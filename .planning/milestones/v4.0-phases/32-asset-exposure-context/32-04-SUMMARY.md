---
phase: 32-asset-exposure-context
plan: 04
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, connectors, exposure-context]

# Dependency graph
requires:
  - phase: 32-asset-exposure-context (Plan 02)
    provides: Real internet_facing v1 proxy ("internet-facing" tag OR external_ip IS NOT NULL) in infer_exposure_context/apply_inference_to_asset, EXPOSURE_FIELDS AUTO-gate
  - phase: 32-asset-exposure-context (Plan 03)
    provides: apply_precedence_to_asset (ASSET_OVERRIDE > GROUP_OVERRIDE > AUTO), the per-field precedence resolver this plan's detected-signal kwarg had to pass through unchanged
provides:
  - NormalizedVulnerability.internet_facing (bool | None) — the per-connector real-signal contract every connector normalize step can set
  - Asset.internet_facing_detected (migration 041) — durable raw vendor provenance column, mirrors external_ip
  - infer_exposure_context(internet_facing_detected=...) precedence — detected signal (when not None) wins over the v1 external_ip/tag proxy; ASSET_OVERRIDE/GROUP_OVERRIDE still permanently wins over both
  - Honest per-connector coverage table (exposure.py module docstring) — all 6 connectors documented FALLBACK this session, with the specific fields inspected and why no real signal exists today
affects: [32-05-frontend-exposure-context, 33-risk-exposure-model, any future connector-schema-confirmation session that adds a real per-connector internet-facing field]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Detected-signal-over-proxy precedence: a nullable raw-provenance column (internet_facing_detected) mirrors external_ip's shape exactly — None means 'no vendor signal', a real bool always wins over the derived proxy formula. Same shape reusable for any future exposure-context field needing a real-vs-proxy split."
    - "Cross-6-connector coverage sweep test (mirrors test_connector_normalization.py's ENRICH-06 shape): one parametrized test exercising every connector's normalize path with a representative payload, asserting a new dataclass field is always explicitly set (never AttributeError) even when every connector's answer is the same (None/FALLBACK)."

key-files:
  created:
    - backend/alembic/versions/041_add_inet_facing_signal.py
    - backend/tests/test_connector_internet_facing.py
  modified:
    - backend/app/assets/models.py
    - backend/app/assets/exposure.py
    - backend/app/connectors/base.py
    - backend/app/connectors/sync.py
    - backend/tests/test_asset_exposure.py

key-decisions:
  - "All 6 connectors (CrowdStrike, Wiz, Qualys, Nessus, Rapid7, Defender) are documented FALLBACK this session — each connector's actual raw payload/GraphQL response shape was inspected directly (not grepped for a field that might already be mapped), and none currently extracts a distinct internet-facing/public-exposure signal. CrowdStrike's device dict has external_ip (already the v1 proxy's own signal — re-deriving internet_facing_detected from it would be circular, not a second signal). Wiz's vulnerableAsset sub-object (both the base and EPSS-enriched GraphQL queries) has no publicExposure/isInternetFacing field. Qualys/Nessus/Rapid7/Defender's host/machine dicts surface only ip/dns/os/health fields into their normalize functions. This matches — and re-confirms via fresh inspection, not just citation — 32-PATTERNS.md's 'No Analog Found' finding and 32-RESEARCH.md's prior conclusion."
  - "The full detected-signal schema spine (dataclass field, Asset column, sync.py create+update passthrough, infer_exposure_context precedence) is landed regardless of the zero-real-signals outcome, per the plan's explicit design: the day a vendor schema is confirmed to expose a genuine signal (e.g. a live Wiz GraphQL introspection), only that one connector's normalize step needs a one-line change — no schema or precedence work remains undone."
  - "sync.py's update-branch passthrough uses `if getattr(v, \"internet_facing\", None) is not None:` (not a truthy check) — this distinguishes a genuine vendor 'False' from 'vendor said nothing,' so a previously-captured real signal is never silently overwritten with None on a subsequent sync from a different/older connector version."
  - "No re-derivation of internet_facing_detected from CrowdStrike's existing external_ip was added — doing so would make the 'detected' column trivially redundant with the proxy it's supposed to be independent from (same underlying fact, not two signals), which would defeat the precedence test's purpose of proving a genuinely distinct signal wins."

requirements-completed: [EXPO-02]  # Final contributing plan — EXPO-02 now fully complete (real per-connector detection landed + honestly documented; Plan 02 already delivered the proxy fallback + precedence skeleton).

# Metrics
duration: ~20min
completed: 2026-08-10
---

# Phase 32 Plan 04: Asset Exposure Context — Real Per-Connector Internet-Facing Detection Summary

**Landed the full detected-signal schema spine (NormalizedVulnerability.internet_facing, Asset.internet_facing_detected, sync passthrough, infer_exposure_context precedence) and, after directly inspecting all 6 connectors' actual raw payload/GraphQL shape, honestly documented that none of them currently exposes a distinct internet-facing signal — every connector stays FALLBACK to the v1 external_ip/tag proxy.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-10T17:05:00Z (approx.)
- **Completed:** 2026-08-10T17:25:00Z
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- Added `NormalizedVulnerability.internet_facing: bool | None = None` to `base.py` — the contract every connector's normalize step can set when (and only when) its raw vendor payload genuinely supports a real internet-facing/public-exposure signal.
- Migration `041_add_inet_facing_signal` adds `Asset.internet_facing_detected` (nullable `Boolean`, no `server_default` — mirrors `external_ip`'s raw-provenance shape exactly, `None` until a connector supplies a real signal). Chains `040 -> 041`; single head confirmed via `alembic heads`; applied to the local dev Postgres.
- `sync.py::_upsert_asset` passthrough in both the create branch (unconditional capture) and the update branch (`if getattr(v, "internet_facing", None) is not None:` — distinguishes a genuine vendor `False` from "vendor said nothing," never silently clobbering a previously-captured real signal with `None`).
- `infer_exposure_context` gained an `internet_facing_detected: bool | None = None` kwarg: when not `None`, it wins over the v1 `external_ip`/tag proxy; when `None` (no connector signal), the exact Plan 02 proxy formula still applies unchanged. Both `apply_inference_to_asset` and `apply_precedence_to_asset` (Plan 03's GROUP_OVERRIDE-aware resolver) pass `asset.internet_facing_detected` through — an `ASSET_OVERRIDE`/`GROUP_OVERRIDE` still permanently wins over both the detected signal and the proxy (EXPO-03/04 unchanged, proven by a dedicated integration test).
- **Inspected all 6 connectors' real raw payload/GraphQL response shape directly** (not a grep for an already-mapped field): CrowdStrike's device dict (`/devices/entities/devices/v2`), Wiz's `vulnerableAsset` sub-object (both `VULNERABILITY_QUERY` and the EPSS-enriched `VULNERABILITY_QUERY_ENRICHED`), Qualys's host list (`/api/2.0/fo/asset/host/`), Nessus's scan/host detail, Rapid7's InsightVM asset resource (`/api/3/assets`), and Defender's machine dict (`/api/machines`) — **zero connectors currently extract a distinct internet-facing/public-exposure signal**. This re-confirms (via fresh inspection this session, not citation) 32-PATTERNS.md's "No Analog Found" finding and 32-RESEARCH.md's prior conclusion.
- Added an honest per-connector coverage table to `exposure.py`'s module docstring, documenting each connector as FALLBACK with the specific field(s) inspected and why no signal was mapped (no field name guessed, per CONTEXT.md's T-32-12 mitigation).
- `test_connector_internet_facing.py`: a cross-6 parametrized sweep (mirrors `test_connector_normalization.py`'s ENRICH-06 shape) proving every connector's normalize path always explicitly sets `internet_facing` (never `AttributeError`) and it is `None` for all 6 on a representative payload.
- Full regression proven green: `test_connector_internet_facing.py` (6) + `test_asset_exposure.py` (25, includes 4 new Plan-04 precedence/override tests) + `test_connector_normalization.py` (28) + `test_asset_groups.py` (3) + `test_asset_owner_reassign.py` (6) + `test_connectors/` (67, all 6 connector-specific suites) + `test_connector_health.py`/`test_vulnerability_enrichment.py` (11) — 146 tests total, 0 failures. mypy-baseline: 0 new violations (no resync needed). Ruff clean on all touched files.

## Task Commits

1. **Task 1: RED — detected-signal-beats-proxy + proxy-fallback + override-permanence tests** - `6c75397` (test)
2. **Task 2: GREEN part 1 — schema spine (migration 041, dataclass field, sync passthrough, inference precedence)** - `fc4b7a9` (feat)
3. **Task 3: GREEN part 2 — per-connector real detection + honest coverage documentation** - `378142b` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `backend/alembic/versions/041_add_inet_facing_signal.py` - `Asset.internet_facing_detected` (nullable `Boolean`, no default), chains `040 -> 041`
- `backend/tests/test_connector_internet_facing.py` - cross-6 connector coverage sweep proving `internet_facing` is always set and honestly `None` for every connector today
- `backend/app/assets/models.py` - `internet_facing_detected` column on `Asset`, docstring cross-reference to exposure.py's coverage table
- `backend/app/assets/exposure.py` - `infer_exposure_context(internet_facing_detected=...)` precedence kwarg; both `apply_inference_to_asset` and `apply_precedence_to_asset` pass it through; module docstring gained the full honest per-connector coverage table
- `backend/app/connectors/base.py` - `NormalizedVulnerability.internet_facing: bool | None = None` field
- `backend/app/connectors/sync.py` - create + update branch passthrough (`internet_facing_detected=getattr(v, "internet_facing", None)` / `is not None` gate on update)
- `backend/tests/test_asset_exposure.py` - 4 new Plan-04 tests: detected-wins-with-no-proxy, detected-False-wins-over-external_ip-proxy, proxy-used-when-detected-is-None, ASSET_OVERRIDE-still-wins-over-a-later-detected-signal

## Decisions Made

- **All 6 connectors documented FALLBACK** — see key-decisions above for the full per-connector inspection rationale. This is a legitimate, honestly-verified outcome explicitly anticipated by the plan ("a connector that legitimately has no signal is a documented FALLBACK, not a failure") and by CONTEXT.md's T-32-12 threat disposition (no field name guessed).
- **Schema spine landed ahead of any confirmed mapping** — the dataclass field, Asset column, sync passthrough, and inference precedence are fully wired now so that a future session confirming a real vendor field needs only a one-line normalize-step change, not new plumbing.
- **CrowdStrike's external_ip NOT re-derived into internet_facing_detected** — would be circular (same fact restated, not a second signal), and would defeat the point of proving a genuinely distinct detected signal beats the proxy.
- **Update-branch passthrough uses an `is not None` gate, not a truthy check** — preserves the distinction between "vendor said False" and "vendor said nothing," so a real signal already captured on the asset is never silently reverted to `None` by a later sync that happens not to carry the field.

## Deviations from Plan

None - plan executed exactly as written. The interfaces block's exact function signatures, migration shape, and dataclass/model field placement were followed as specified. Task 3's per-connector inspection concluded "zero real signals found" rather than "some connectors get real signals" — this is a valid, plan-anticipated outcome (the plan's own objective describes the work as "exploratory" and explicitly permits an honest FALLBACK-everywhere conclusion), not a deviation requiring a Rule 4 architectural check-in.

## Issues Encountered

None beyond the expected local-dev-DB migration apply (`alembic upgrade head`) needed before the new-column integration test could pass — routine for this codebase's schema-change workflow, not a plan deviation.

## User Setup Required

None - no external service configuration required. Migration `041_add_inet_facing_signal` was applied to the local dev Postgres (`alembic upgrade head`) as part of verification; a production/staging deploy still needs to run the same migration through its normal deploy pipeline.

## Next Phase Readiness

EXPO-02 is now fully complete: real per-connector internet-facing detection is wired end-to-end (schema, sync, precedence) and honestly documented as FALLBACK-everywhere for the current connector set, with zero remaining plumbing work for whichever future session confirms a real vendor field. Ready for:
- Plan 05 (frontend) — surfaces `internet_facing`/`internet_facing_source` (already exposed since Plan 01) exactly as before; no frontend-visible change from this plan (the detected-vs-proxy precedence is entirely a backend inference-time concern, invisible to the API response shape).
- Phase 33 (risk-exposure model) — consumes the same materialized `internet_facing` column; this plan changes only how that column is computed, not its shape or meaning.

No blockers.

## Known Stubs

None. `Asset.internet_facing_detected` being universally `None` in production today is not a stub — it is the honestly-documented, inspected-and-confirmed current state of all 6 connectors' vendor payloads, explicitly anticipated by the plan and recorded in `exposure.py`'s coverage table for future re-verification.

## Threat Flags

None - the one new trust boundary (vendor payload → `NormalizedVulnerability.internet_facing` → `Asset.internet_facing_detected`) was explicitly covered by this plan's `<threat_model>` (T-32-11: signal coerced to bool|None at the parser, only the AUTO-gated materialized `internet_facing` column feeds downstream logic, admin override always wins; T-32-12: accepted via the inspect-don't-guess process, satisfied by this session's direct per-connector inspection). No additional network endpoints, auth paths, or schema changes at trust boundaries beyond the plan's specified migration.

---
*Phase: 32-asset-exposure-context*
*Completed: 2026-08-10*

## Self-Check: PASSED

All 7 created/modified key files verified present on disk; all 3 task commit hashes (`6c75397`, `fc4b7a9`, `378142b`) verified present in `git log`.
