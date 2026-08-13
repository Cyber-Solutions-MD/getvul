---
phase: 35-source-aware-filtering-provenance-badges
verified: 2026-08-13T07:49:08Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:

  - test: "Live-browser visual check that SourceBadgeGroup never reads as 'confirmed' across Vulnerabilities/Assets/CSPM/Tickets, and that the OR/AND source_mode toggle visibly disables below 2 selections on each surface"
    expected: "Single-source badge shows one neutral-chrome provider mark (colored gradient, no green corroboration tint/checkmark/copy); 2+ source badge shows the mark group + 'N sources' green-tinted label; toggle greys out / no-ops below 2 selected sources"
    why_human: "No browser available in this session — verified only at the component/unit-test level (vitest, jsdom). Explicitly deferred to phase UAT by every plan's own <verification> block (35-02, 35-05 SUMMARYs)."

  - test: "WCAG AA axe sweep on the corroboration tint (rgba(74,222,128,...) + var(--color-success)) and the provider-mark glyphs against their backgrounds"
    expected: "Contrast ratios pass AA for text/glyph vs. background across all 6 scanner gradients and the neutral fallback mark"
    why_human: "Per project memory (getvul-axe-sweep-not-run-during-exec), the Playwright axe sweep requires a prod build + running server and was not executed this session; treated as accepted debt, not a blocker, per the phase's explicit scope."
---

# Phase 35: Source-Aware Filtering & Provenance Badges Verification Report

**Phase Goal:** Every finding/asset/CSPM/ticket row shows honest, non-overclaiming source provenance, and analysts get real per-entity OR/AND scanner-source filtering. FINAL phase of v4.0.
**Verified:** 2026-08-13T07:49:08Z
**Status:** passed (visual UAT + axe waived on-trust at v4.0 closeout, 2026-08-13)

## Accepted debt (v4.0 closeout)

All 8 SRC must-haves are verified in code and by live-run suites (backend 22 + frontend 199+18 tests).
The only open items are the live-browser visual UAT of the SourceBadgeGroup + source chips across the
four surfaces, and the WCAG AA axe sweep (needs a prod build+server) — both waived on-trust, consistent
with the on-trust waivers in Phases 24–27 (v3.0) and 31–34 (v4.0). Close by running the axe sweep +
a visual pass on a live stack. A3 (badge corroboration tint) is a reviewable design choice, not a defect.
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every finding row shows a SourceBadgeGroup distinguishing single- vs multi-source-corroborated; never implies "confirmed" | ✓ VERIFIED | `frontend/src/components/vulnerabilities/source-badge-group.tsx` read in full: single-source (`n<=1`) branch renders bare marks with zero corroboration chrome; multi-source (`n>=2`) branch adds the green-tinted "N sources" wrapper. Grepped entire component: no "confirmed"/"verified" string anywhere. `source-badge-group.test.tsx` (6 tests) + wired into `vuln-table.tsx`, `assets-table.tsx`, `cspm/finding-card.tsx`, `tickets-table.tsx` (grep confirms all 4 import/render it). All 4 surfaces' component test suites pass live (see Behavioral Spot-Checks). |
| 2 | Vulnerabilities + Assets OR default (`&&`)/AND toggle (`@>`) via correlation ARRAY, `source_mode` HTTP-reachable; Assets partitions scanner vs enrichment; shipped assets multi-select-ANDs bug FIXED w/ regression test; SRC-02 delivered for all 4 entities incl. Tickets (real filter) | ✓ VERIFIED | `app/vulnerabilities/service.py:52-54` uses `.contains()`/`.overlap()` on `VulnerabilityCorrelation.sources`; `source_mode` bound in `vulnerabilities/router.py:86,134` and `cspm/router.py:55,67`. `app/assets/router.py:175-208` replaced the chained-`.where()` AND bug with `or_(*contains)` OR-default + explicit AND branch; `app/assets/constants.py` partitions `SCANNER_SOURCES`/`ENRICHMENT_SOURCES`; `ticketing/rule_engine.py:77-85` fixes the identical bug importing the same constants. `ticketing/router.py:178,200` binds a real `?source=` list param into `list_tickets`. Ran `test_source_filtering.py` (6/6 pass), `test_asset_source_filter.py` (6/6 pass incl. `test_or_default_multi_scanner_returns_union` — the literal bug-regression test), `test_vuln_source_filter.py` (4/4 regression pass), `test_rule_engine.py` (9/9 regression pass). |
| 3 | CSPM true multi-tool AND corroboration via read-time `GROUP BY(tenant_id,rule_id,resource_id) HAVING count(DISTINCT source)` — no silent OR | ✓ VERIFIED | `app/cspm/service.py:41-55` — AND branch (`source_mode=="and" and len>=2`) builds the `GROUP BY(rule_id,resource_id) HAVING count(DISTINCT source)>=len(selected)` subquery; OR path stays a plain `source.in_()`, structurally separate code paths (grepped: no shared branch). Ran `test_cspm_corroboration.py` (5/5 pass), including `test_cspm_and_requires_same_group` (3-group fixture proving the GATE is the group key, not result-set membership) and `test_cspm_and_reaches_service_via_http` (proves `source_mode` isn't dropped by FastAPI param binding). |
| 4 | Ticket provenance resolves transitively through the linked vuln's correlation (union rule); tested | ✓ VERIFIED | `app/ticketing/service.py:915` uses `func.array_agg(func.distinct(Vulnerability.source))` for `own_sources` (a real SQL union, not `func.min`); `:958-981` batches a `VulnerabilityCorrelation` fetch and `_resolve_sources()` unions per grouped-ticket-url. Ran `test_source_provenance_batched.py` (5/5 pass): `test_ticket_transitive_provenance`, `test_ticket_grouped_union` (2-vuln mixed-corroboration union), `test_ticket_single_source_no_correlation`, `test_ticket_list_filter_by_source`, `test_list_tickets_query_count_invariant`. |
| 5 | Provenance + source-facet queries batched (no per-row N+1), proven with query_count.py, page-size-invariant | ✓ VERIFIED | `backend/tests/query_count.py` exists (`before_cursor_execute` context manager). All 4 query-count-invariance tests ran and passed live: `test_source_filtering.py::test_list_query_count_is_page_size_invariant`, `test_asset_source_filter.py::test_list_assets_query_count_invariant`, `test_cspm_corroboration.py::test_cspm_query_count_invariant`, `test_source_provenance_batched.py::test_list_tickets_query_count_invariant`. Batching shapes confirmed by direct code read: `tuple_(...).in_(page_keys)` in vulnerabilities/service.py, in-Python derivation (zero extra query) in assets/router.py, `tuple_((rule_id,resource_id)).in_(page_keys)` grouped fetch in cspm/service.py, and the 2-extra-query ticket batch in ticketing/service.py. |
| 6 | Alembic single head 045; frontend SOURCES has no fake TENABLE/AWS_INSPECTOR/MOCK, includes real NESSUS/DEFENDER | ✓ VERIFIED | `alembic heads` and `alembic current` both report `045_add_seen_by_sources_gin (head)` — single head, matches DB state. `grep -rl "TENABLE\|AWS_INSPECTOR\|MOCK"` across all 4 production component dirs (excluding `.test.tsx`) returns zero matches. `chip-bar.tsx:32` and `assets-chip-bar.tsx:42` both list exactly `['CROWDSTRIKE','NESSUS','DEFENDER','WIZ','QUALYS','RAPID7']`, matching `backend/app/vulnerabilities/models.py:32-38`'s `VulnSource` enum verbatim. |
| 7 | `source_mode` bound in vulnerabilities/router.py + cspm/router.py; `?source=` exists in ticketing/router.py | ✓ VERIFIED | Direct grep confirms all 3 bindings (see truth #2 evidence) plus `assets/router.py:131` (`source_mode` as raw `Query(str)` param, 422 on bad value). |
| 8 | Requirements SRC-01..08 cross-referenced against REQUIREMENTS.md | ✓ VERIFIED | REQUIREMENTS.md lines 53-60 mark all 8 as `[x]` complete, and lines 118-125 map all 8 to "Phase 35 ... Complete" in the traceability table. Every SRC-ID has ≥1 passing automated test (see coverage table below). |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/tests/query_count.py` | `before_cursor_execute` harness | ✓ VERIFIED | Read in full; matches interfaces contract exactly; reused verbatim by 3 downstream test files (grepped imports). |
| `backend/tests/test_source_filtering.py` | Vuln OR/AND + sources + query-count tests | ✓ VERIFIED | 6/6 tests pass live. |
| `backend/tests/test_asset_source_filter.py` | Assets bug regression + partition + query-count | ✓ VERIFIED | 6/6 tests pass live. |
| `backend/tests/test_cspm_corroboration.py` | CSPM AND-grouping + query-count | ✓ VERIFIED | 5/5 tests pass live. |
| `backend/tests/test_source_provenance_batched.py` | Ticket transitive union + query-count | ✓ VERIFIED | 5/5 tests pass live. |
| `backend/app/vulnerabilities/{schemas,service,router}.py` | `source_mode` + `sources`/`sources_count` + `&&`/`@>` branch | ✓ VERIFIED | `sources.overlap`/`sources.contains` present; router binds `source_mode`. |
| `backend/app/assets/constants.py` | `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` frozensets | ✓ VERIFIED | Present, imported by both `assets/router.py` and `ticketing/rule_engine.py`. |
| `backend/alembic/versions/045_add_seen_by_sources_gin.py` | GIN index migration, head 045 | ✓ VERIFIED | File read; `alembic heads`/`current` confirm single head 045. |
| `backend/app/cspm/{schemas,service,router}.py` | `source_mode` + GROUP BY/HAVING AND + batched group sources | ✓ VERIFIED | `group_by`/`having`/`array_agg` present in service.py; `source_mode` bound in router.py. |
| `backend/app/ticketing/{schemas,service,router}.py` | `sources`/`sources_count` + `array_agg` union + real `?source=` filter | ✓ VERIFIED | `array_agg(func.distinct(...))` present, no `func.min` used for provenance; router binds `source` list param. |
| `frontend/src/components/vulnerabilities/source-badge-group.tsx` (+test) | Shared non-overclaiming component | ✓ VERIFIED | Read in full; 6 tests pass live; literal `SOURCE_GRADIENTS`/`SOURCE_GLYPH` maps, no string concatenation, no `<img>`, unknown-code neutral fallback. |
| `frontend/src/components/vulnerabilities/{vuln-table,chip-bar}.tsx` | SourceBadgeGroup + reconciled SOURCES + OR/AND toggle | ✓ VERIFIED | Both wired; 18 tests pass live (source-badge-group + chip-bar). |
| `frontend/src/components/assets/{assets-chip-bar,assets-table}.tsx` | Split scanner/enrichment axes + SourceBadgeGroup | ✓ VERIFIED | Both axes present; wired through `use-assets.ts` + `assets/page.tsx` (grep confirms end-to-end URL-param threading). |
| `frontend/src/app/(authed)/dashboard/cspm/page.tsx` + `finding-card.tsx` | source_mode toggle + SourceBadgeGroup | ✓ VERIFIED | Both present; wired through `use-cspm-findings.ts`. |
| `frontend/src/components/tickets/{tickets-chip-bar,tickets-table}.tsx` | Real `?source=` axis + SourceBadgeGroup | ✓ VERIFIED | Both present; wired through `use-tickets.ts` (repeated-param shape matching backend `list[str]` binding) + `tickets/page.tsx`. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `vulnerabilities/router.py` | `VulnerabilityFilter.source_mode` | `Query(...)` param bound into filter construction | WIRED | `source_mode=source_mode` at router.py:134 |
| `cspm/router.py` | `MisconfigFilter.source_mode` | `Query(...)` param bound | WIRED | `source_mode=source_mode` at router.py:67; `test_cspm_and_reaches_service_via_http` proves HTTP reachability end-to-end |
| `ticketing/router.py` | `list_tickets(source=...)` | `Query(None)` param passed through | WIRED | router.py:178,200; `test_ticket_list_filter_by_source` proves it's a real filter, not display-only |
| `assets-chip-bar.tsx`/`cspm/page.tsx`/`tickets-chip-bar.tsx` | backend query params | `use-{assets,cspm-findings,tickets}.ts` + surface `page.tsx` | WIRED | Grep-traced: chip-bar writes URL state → page.tsx reads it → query hook serializes into the exact param shape (CSV vs repeated) the backend router expects. Explicitly confirmed via 35-05-SUMMARY's Rule-3 fix-log and independently re-verified here by grep. |
| `{assets,cspm,tickets}` rows | `source-badge-group.tsx` | `<SourceBadgeGroup sources={...} count={...}/>` | WIRED | Grep confirms import + render call in all 4 surface files. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | -------------- | ------ | ------------------- | ------ |
| `vuln-table.tsx` | `row.sources`/`row.sources_count` | `list_vulnerabilities` batched correlation fetch | Yes — real DB query, tenant-scoped, page-scoped `tuple_(...).in_()` | ✓ FLOWING |
| `assets-table.tsx` | `row.sources`/`row.sources_count` | in-Python derivation from already-selected `seen_by_sources` column | Yes — no query needed, real column data | ✓ FLOWING |
| `finding-card.tsx` | `finding.sources`/`finding.sources_count` | `list_misconfigurations` page-scoped `GROUP BY` fetch | Yes — real DB aggregate, tenant-scoped | ✓ FLOWING |
| `tickets-table.tsx` | `row.sources`/`row.sources_count` | `list_tickets` batched `array_agg` + `VulnerabilityCorrelation` union | Yes — real DB aggregates, tenant-scoped, verified by `test_ticket_grouped_union`'s mixed-corroboration fixture | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Vuln OR/AND + sources response + query-count | `pytest tests/test_source_filtering.py -v` | 6 passed | ✓ PASS |
| Assets OR-default bug regression + partition + query-count | `pytest tests/test_asset_source_filter.py -v` | 6 passed | ✓ PASS |
| CSPM AND-grouping (no silent OR) + query-count | `pytest tests/test_cspm_corroboration.py -v` | 5 passed | ✓ PASS |
| Ticket transitive union + real filter + query-count | `pytest tests/test_source_provenance_batched.py -v` | 5 passed | ✓ PASS |
| Regression: pre-existing vuln source filter | `pytest tests/test_vuln_source_filter.py -v` | 4 passed | ✓ PASS |
| Regression: rule engine (asset-match bug fix site) | `pytest tests/test_rule_engine.py -v` | 9 passed | ✓ PASS |
| Frontend: SourceBadgeGroup + vuln chip-bar | `npx vitest run source-badge-group.test.tsx chip-bar.test.tsx` | 18 passed | ✓ PASS |
| Frontend: Assets/CSPM/Tickets surfaces + query hooks | `npx vitest run src/components/{assets,cspm,tickets}/ "cspm/page" use-assets.test.ts use-cspm-findings.test.ts use-tickets.test.ts` | 199 passed (31 files) | ✓ PASS |
| Alembic single head | `alembic heads` / `alembic current` | `045_add_seen_by_sources_gin (head)` both | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| SRC-01 | 01, 02, 03, 04, 05 | Source-provenance badge, non-overclaiming | ✓ SATISFIED | `source-badge-group.tsx` structural check + 4-surface wiring + `sources`/`sources_count` data spine on all 4 backend entities |
| SRC-02 | 01, 03, 04, 05 | Scanner-source filter on all 4 entities | ✓ SATISFIED | `source_mode`/`scanner`/`source` params bound in all 4 routers; real filters (not display-only) proven by tests incl. `test_ticket_list_filter_by_source` |
| SRC-03 | 01, 02, 03 | OR default (union) | ✓ SATISFIED | `test_or_default_returns_union`, `test_or_default_multi_scanner_returns_union` (the literal bug regression), `test_cspm_or_default_unchanged` |
| SRC-04 | 01, 02, 03, 04 | AND toggle (corroboration-only) | ✓ SATISFIED | `test_and_toggle_requires_corroboration`, `test_and_toggle_requires_all`, `test_cspm_and_requires_same_group`, `test_cspm_and_reaches_service_via_http` |
| SRC-05 | 04 | CSPM true multi-tool AND via GROUP BY | ✓ SATISFIED | `test_cspm_and_requires_same_group`; code read confirms no `source.in_()` fallback for AND |
| SRC-06 | 03, 05 | Assets scanner/enrichment partition | ✓ SATISFIED | `test_enrichment_does_not_leak_into_scanner_filter`; frontend split axes in `assets-chip-bar.tsx` |
| SRC-07 | 04 | Ticket transitive provenance union | ✓ SATISFIED | `test_ticket_transitive_provenance`, `test_ticket_grouped_union` |
| SRC-08 | 01, 03, 04 | Batched, no-N+1, page-size invariant | ✓ SATISFIED | 4 query-count-invariance tests pass; `query_count.py` harness confirmed |

No orphaned requirements found — all 8 SRC-IDs map cleanly to plans that claimed them (REQUIREMENTS.md traceability table lines 118-125 lists exactly these 8, all "Complete").

### Anti-Patterns Found

None. Grepped all 20 touched production files (backend schemas/service/router files across 4 entities + frontend badge/chip-bar/table/card files) for `TODO|FIXME|XXX|HACK|not yet implemented|not available|coming soon` — zero matches.

### Human Verification Required

### 1. Live-browser visual check across all 4 surfaces

**Test:** Load Vulnerabilities, Assets, CSPM, and Tickets pages with seeded single-source and multi-source-corroborated data; visually confirm the SourceBadgeGroup on each surface, and toggle the OR/AND `source_mode` control.
**Expected:** Single-source badge = one neutral-chrome (no green tint/checkmark) provider mark; multi-source badge = mark group + green "N sources" label; never any "confirmed"/"verified" text; the OR/AND toggle visibly disables/no-ops below 2 selected sources on Vulnerabilities/Assets/CSPM (Tickets has no toggle, by design).
**Why human:** No browser was available this session. Component/unit tests (vitest+jsdom) prove the underlying render logic is correct in isolation, but live cross-surface visual consistency and interaction feel were not observed. Every plan's own `<verification>` block explicitly defers this to phase UAT (35-02/35-05 SUMMARYs both state this directly, not just as an assumption).

### 2. WCAG AA axe sweep on the corroboration tint + provider marks

**Test:** Run the Playwright axe sweep (prod build + running server) against pages rendering SourceBadgeGroup.
**Expected:** AA contrast pass for the `rgba(74,222,128,...)`/`var(--color-success)` tint and all provider-mark glyphs against their gradient backgrounds.
**Why human:** Per project memory (`getvul-axe-sweep-not-run-during-exec`), this sweep was never run during execution and requires infrastructure (prod build + server) not available in this verification session. This is accepted debt per the task's own framing, not a new gap — flagged here for completeness rather than silently omitted.

### Accepted Debt (not failures)

- Live visual UAT of badges/chips across all 4 surfaces — no browser this session (see Human Verification #1).
- WCAG AA axe sweep — not run (see Human Verification #2; consistent with project memory on this recurring gap class).
- The A3 badge corroboration color (SLA-ok green reused for corroboration meaning) is a reviewable design choice per CONTEXT.md's own framing, not a defect — it was implemented exactly as specified and is intentionally flagged there as "reviewable," not "unresolved."

### Gaps Summary

No blocking gaps. All 8 SRC requirements have passing, live-run automated tests (26 backend tests across 4 new suites + 2 regression suites, 199+18 frontend tests across all 4 surfaces). Alembic is at a single head (045). All router bindings for `source_mode`/`scanner`/`source` were directly grepped and confirmed reachable via HTTP, closing the exact "silently dropped by explicit-Query-param routers" failure mode the plans repeatedly flagged as a risk. The only open items are the two pieces of explicitly pre-accepted debt (live visual UAT, axe sweep) that this phase's own plans deferred to UAT from the start — hence `status: human_needed` rather than `gaps_found`.

---

*Verified: 2026-08-13T07:49:08Z*
*Verifier: Claude (gsd-verifier)*
