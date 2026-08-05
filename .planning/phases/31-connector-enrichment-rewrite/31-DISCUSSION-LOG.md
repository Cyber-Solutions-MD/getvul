# Phase 31: Connector Enrichment Rewrite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-05
**Phase:** 31-connector-enrichment-rewrite
**Areas discussed:** EPSS/KEV data flow, Vendor priority columns, source_signals encoding, Daily job resilience

---

## EPSS/KEV data flow

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot at ingest + daily re-propagate | Connector copies EPSS/KEV onto the finding; daily job bulk-UPDATEs existing findings from refreshed ref table. Faithful to SC#1, fast list sort/filter, adds propagation write path. | ✓ |
| Read-time join, ref table is truth | Findings store only cve_id; values JOINed at query time. Zero staleness/backfill but large read-path blast radius; per-finding columns become dead. | |
| Hybrid: KEV read-time, EPSS snapshot | Split by access pattern; two mechanisms to maintain. | |

**User's choice:** Snapshot at ingest + daily re-propagate.
**Notes:** Daily UPDATE is unconditional on cve_id → historical findings backfill for free. Flagged that `epss_percentile` needs a new column (model only has `epss_score`).

### KEV authority (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Ref table is sole authority | finding.cisa_kev = (cve ∈ CISA KEV catalog); connector guesses discarded from column, preserved in source_signals. Cleanest ENRICH-02 fix. | ✓ |
| OR ref table with connector guess | catalog_hit OR connector_said_true — re-admits the inconsistency ENRICH-02 kills. | |

**User's choice:** Ref table is sole authority.
**Notes:** Defender `cisa_kev=False` hardcode becomes moot (overridden by fact); connector native KEV signal retained in source_signals for provenance.

---

## Vendor priority columns

| Option | Description | Selected |
|--------|-------------|----------|
| Generic pair, raw values preserved | `native_priority_score` (Numeric raw) + `native_priority_rating` (String raw); `source` col disambiguates scale; weighting deferred to Phase 33. Every finding populated. | ✓ |
| Vendor-specific typed columns | nessus_vpr, exprt_rating, exprt_score, qualys_qds, rapid7_risk_score… — faithful but ~8–10 sparse cols, no mixed-scanner sort. | |
| Generic pair, normalized to 0–100 now | Cross-scanner comparable today but bakes a scoring opinion that belongs to Phase 33. | |

**User's choice:** Generic pair, raw values preserved.
**Notes:** Each finding is single-source, so vendor-specific columns would be maximally sparse; normalization is Phase 33's job (defer, don't opine). Raw vendor label stored verbatim in `native_priority_rating`.

---

## source_signals encoding

| Option | Description | Selected |
|--------|-------------|----------|
| Omission = missing | Only vendor-returned keys written; absent → missing, present-false/0 → negative. JSONB idiom, mirrors mdm_details, trivial SC#4 fixture, `?` operator queryable. | ✓ |
| Explicit null sentinel | Every known field always keyed; null → missing. Self-documenting but brittle as payloads evolve. | |
| {value, present} wrapper | Per-field object with presence flag. Verbose, bloated, awkward to query. | |

**User's choice:** Omission = missing.

### What populates source_signals (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Curated per-connector allowlist | Each connector captures its risk/exploit/priority-relevant fields, keyed by raw vendor field name; promoted fields not duplicated. Intentional, queryable, no bloat. | ✓ |
| Dump entire raw record minus promoted | Maximally lossless but bloat/PII risk, unpredictable queryability. | |

**User's choice:** Curated per-connector allowlist.

---

## Daily job resilience

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic swap, keep last-good | Replace ref table only on fully-successful fetch+parse; failure keeps last-good + logs; ingestion never blocks. | ✓ |
| In-place upsert, best-effort | Row-by-row upsert; truncated feed leaves mixed old+new state observable to reads. | |

**User's choice:** Atomic swap, keep last-good.
**Notes:** EPSS/KEV drift slowly, one missed day harmless; re-propagation runs next successful day.

### Cold-start / bootstrap (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Eager first-run + self-healing daily | On startup, refresh immediately if empty/stale >24h; leftover nulls self-heal via daily re-propagation UPDATE. | ✓ |
| Wait for daily tick, rely on self-heal | Simpler single path but multi-hour null-EPSS/KEV window. | |

**User's choice:** Eager first-run + self-healing daily.

---

## Claude's Discretion

- New-column nullability/defaults, sort indexes, Alembic revision chaining, ref-table PK/index shape.
- Exact EPSS (FIRST.org CSV) / CISA KEV (JSON catalog) feed endpoints + parse details.
- Precise scheduler wiring (extractable async def + 24h-gate variable) following existing idioms.
- Per-connector allowlist field sets (bounded by D-05/D-07/D-08).
- Whether re-propagation + eager refresh reuse the `backfill_sla_due_dates` bulk-UPDATE idiom.

## Deferred Ideas

- Cross-scanner normalization/weighting of native priority signals → Phase 33.
- Cross-vendor `native_priority_rating` vocabulary unification → Phase 33.
- Consuming these signals in a per-finding risk score → Phase 33 (define) + Phase 34 (cutover).
- Source-provenance badges & per-entity source filtering → Phase 35.
- Vendor/third-party ML exploit-prediction as a signal → RISK-11 (v2, future).
