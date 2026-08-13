# Phase 31: Connector Enrichment Rewrite - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Every one of the 6 vulnerability connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) captures and persists the richer native signal each scanner actually provides — EPSS score+percentile, real CISA KEV, and vendor-native exploitability/priority signals (Nessus VPR, CrowdStrike ExPRT.AI, Qualys QDS, Rapid7 Risk Score, etc.) — threading them from the raw vendor payload through ingestion into promoted typed columns plus a queryable `source_signals` JSONB, instead of flattening everything to two lossy booleans (`exploit_available`, `cisa_kev`) with `epss_score` populated by nobody. New **global, tenant-independent** `epss_scores` / `cisa_kev` reference tables are refreshed by a dedicated daily job in the existing in-process scheduler, decoupled from any connector's sync cadence.

Requirements ENRICH-01 … ENRICH-06. Success criteria are locked by ROADMAP.md Phase 31. This discussion clarifies HOW to implement them; it does not add capability.

**Out of scope (later phases):** Consuming these signals in a risk-exposure score, and any cross-scanner *weighting/normalization* of the native priority signals → Phase 33 (define) / Phase 34 (recompute+cutover). Asset exposure context → Phase 32. Source-provenance badges and per-entity source filtering → Phase 35.

</domain>

<decisions>
## Implementation Decisions

### EPSS / KEV data flow
- **D-01:** EPSS/KEV are **snapshotted onto each finding at ingest** (connector copies the value from the global ref table into the finding's own `epss_score`/`cisa_kev` columns), **and** the daily job **bulk-re-propagates** the refreshed ref-table values to existing findings via `UPDATE vulnerabilities … FROM epss_scores WHERE cve_id = …`. Rationale: SC#1 requires the value "populated on the finding"; plain per-finding columns keep list sort/filter fast at scale (and set up RISK-02's "sort by most urgent finding"); EPSS scores drift daily so a re-propagation write path is required to avoid permanent staleness. Chosen over read-time JOIN (larger read-path blast radius, makes existing columns dead) and hybrid split. — **Reversibility:** costly — the per-finding columns + propagation UPDATE become load-bearing for downstream sort/filter; moving to a read-time-join model later would touch every list/sort query.
- **D-02:** The unconditional daily re-propagation UPDATE (keyed on `cve_id`, not "ingested this run") **also backfills historical findings** for free — no separate one-time historical-backfill migration is needed for EPSS/KEV. — **Reversibility:** reversible.
- **D-03:** SC#1 requires EPSS score **and percentile**, but `Vulnerability` only has `epss_score` today (`models.py:56`). Add a new **`epss_percentile`** typed column alongside it. — **Reversibility:** one-way — new Postgres column (additive migration); dropping it later needs a reverse migration.
- **D-04:** For a finding's `cisa_kev` column, the **CISA KEV reference table is the sole authority**: `finding.cisa_kev = (cve_id ∈ KEV catalog)`. Every connector's own KEV-ish guess (CrowdStrike `exploit_status ≥ 50`, Wiz `hasCisaKevExploit`, Defender's hardcoded `False`) is **discarded from the column** — this is exactly how ENRICH-02 fixes the Defender hardcode: fact overrides guess, one consistent definition across all 6 scanners. The connector's native KEV-ish signal is still preserved in `source_signals` for provenance (never lost, just not authoritative for the column). Rejected OR-ing the catalog with the connector guess (re-admits the cross-scanner inconsistency ENRICH-02 exists to kill). — **Reversibility:** costly — inverts today's per-connector KEV derivation logic across all 6 connectors.

### Vendor exploitability / priority columns (ENRICH-03)
- **D-05:** Native priority signals land in a **generic two-column pair every finding populates** — `native_priority_score` (Numeric, the **raw** vendor number on its own scale) + `native_priority_rating` (String, the **raw** vendor category verbatim). The existing single-valued `source` column disambiguates which scale/vocabulary applies (each finding belongs to exactly one scanner, so a finding only ever carries one scanner's native signal). Chosen over ~8–10 sparse vendor-specific columns (`nessus_vpr`, `exprt_rating`, …), which would each be null for 5/6 of findings and give no single sortable mixed-scanner column. — **Reversibility:** one-way — new typed columns (additive migration); connectors write into them.
- **D-06:** **Cross-scale normalization/weighting is deliberately DEFERRED to Phase 33.** This phase captures the native values *faithfully and raw*; it does NOT normalize VPR-0–10 vs Rapid7-0–1000 vs ExPRT-categorical onto a common scale. Rejected the "normalize to 0–100 now" option specifically because choosing that mapping is a scoring opinion that belongs to the risk model — baking it here risks locking a formula Phase 33/34 then has to unwind. `native_priority_rating` also stores the raw vendor label verbatim; any cross-vendor rating-vocabulary unification is Phase 33's call. — **Reversibility:** reversible (Phase 33 adds the normalization layer on top of these raw columns).

### `source_signals` JSONB (ENRICH-04)
- **D-07:** **Omission = missing.** Only keys the vendor actually returned are written to `source_signals`. Key absent → "missing" (vendor never returned it); key present with `false`/`0` → "negative" (vendor returned it falsy). Natural JSONB idiom, mirrors the sparse `Asset.mdm_details` precedent, and makes the SC#4 fixture trivial and unambiguous (`assert 'vpr' not in signals` vs `assert signals['exploit_verified'] is False`). Presence is queryable via the Postgres `?` operator. Rejected explicit-null-sentinel (brittle — must enumerate every possible vendor field and write nulls) and `{value, present}` wrapper (verbose/over-engineered). — **Reversibility:** costly — the encoding convention is baked into every connector's write and the SC#4 fixture; changing it re-touches all 6 connectors.
- **D-08:** `source_signals` is populated from a **curated per-connector allowlist** — each connector explicitly captures its risk/exploit/priority-relevant vendor fields, **keyed by the raw vendor field name** (traceable back to the payload). Fields already promoted to columns (cve, cvss, severity, epss, kev, native_priority) are **not** duplicated into `source_signals`. Rejected "dump entire raw record minus promoted" (bloat risk, re-stores host/PII already modeled elsewhere, unpredictable queryability). Adding a field later is a one-line per-connector change. — **Reversibility:** reversible (allowlist is easy to extend).

### Daily reference-data refresh job (ENRICH-05)
- **D-09:** The daily refresh uses an **atomic swap that keeps last-good** data: it fetches+parses the full feed and only replaces the ref-table contents on a fully-successful fetch+parse; any failure or partial/truncated feed leaves the previous good data intact and logs/flags the miss (`feed_refresh_failed`). **Connector syncs and ingestion NEVER block on the feed** — they read whatever is currently in the ref table (possibly a day stale, harmless since EPSS/KEV drift slowly). Rejected in-place best-effort upsert (a truncated feed leaves a mixed old+new state observable to concurrent reads). — **Reversibility:** reversible.
- **D-10:** **Eager first-run + self-healing daily** for the cold-start gap: on scheduler startup, if the ref table is empty or stale (>24h), run the refresh immediately rather than waiting up to a day for the first scheduled tick — minimizing the window where fresh findings ingest null EPSS/KEV. Any findings that still ingested null in that window are self-healed by D-01's unconditional daily re-propagation UPDATE. Belt-and-suspenders; mirrors the scheduler's existing 24h-gated tick idioms. — **Reversibility:** reversible.
- **D-11:** The `epss_scores` / `cisa_kev` reference tables are **global — no `tenant_id`** (a deliberate, ENRICH-05-signed-off exception to the "every table has tenant_id" convention, correct because these are CVE-level facts, not tenant-owned data). — **Reversibility:** one-way — schema shape; adding tenant scoping later would be a redesign.

### Claude's Discretion
- Exact new-column nullability/defaults, index choices (e.g. whether `native_priority_score`/`epss_score` get btree indexes for sort — likely yes given RISK-02 intent), Alembic revision chaining, and ref-table PK/index shape (cve_id-keyed).
- Exact external feed endpoints + parse details for EPSS (FIRST.org daily CSV, ~200k CVEs) and CISA KEV (CISA JSON catalog, ~1.2k CVEs) — researcher/planner to pin the authoritative URLs and formats.
- Precise scheduler wiring of the daily job (which extractable `async def` + 24h-gate variable) following the existing `_last_ticket_sync` / snapshot idioms in `scheduler.py`.
- Exact per-connector allowlist field sets (which raw vendor fields each connector routes to `source_signals` vs promotes) — bounded by D-05/D-07/D-08.
- Whether the re-propagation UPDATE (D-01) and eager refresh (D-10) reuse the `backfill_sla_due_dates` bulk-`UPDATE … FROM` + scheduler-tick idiom (encouraged; same family as RISK-07's cited pattern).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 31: Connector Enrichment Rewrite" — goal, dependencies (independent of Phase 30; both land before Phase 33), and the 5 locked success criteria.
- `.planning/REQUIREMENTS.md` — ENRICH-01 … ENRICH-06.

### Data model under change
- `backend/app/vulnerabilities/models.py` §`Vulnerability` (lines 46–81) — existing `epss_score` (56), `exploit_available`/`cisa_kev` booleans (57–58), `exploit_status_id`/`exploit_status_name` (70–71), `file_paths` JSONB (73). New columns land here: `epss_percentile`, `native_priority_score`, `native_priority_rating`, `source_signals` JSONB.
- `backend/app/assets/models.py:67` — `mdm_details: Mapped[dict | None] = mapped_column(JSONB, default=dict)` — the **precedent to mirror** for the `source_signals` JSONB column (ENRICH-04 names it explicitly).
- New global ref tables `epss_scores` / `cisa_kev` (no `tenant_id`, D-11) — new Alembic migration under `backend/alembic/versions/`.

### Ingestion path (all 6 connectors thread through here — ENRICH-06)
- `backend/app/connectors/base.py` §`NormalizedVulnerability` (lines 9–43) — the normalized dataclass; add fields for `native_priority_score`/`native_priority_rating`/`source_signals` (and confirm epss/kev passthrough).
- `backend/app/connectors/sync.py` §`_upsert_vulnerability` (lines 313–367) — the single write path mapping `NormalizedVulnerability` → `Vulnerability` (both the `existing.*` update branch ~328–337 and the `Vulnerability(...)` insert branch ~340–360). New fields join both branches.
- Per-connector parsers (each captures its native signal + populates the allowlist): `backend/app/connectors/crowdstrike.py` (ExPRT.AI, `exploit_status`; see 353–407), `nessus.py` (VPR; `_check_exploit_available` 233–265), `defender.py` (fix `cisa_kev=False` hardcode 257–274), `wiz.py` (280–283), `qualys.py` (QDS; `_kb_exploit_available` 526–593), `rapid7.py` (Risk Score; 227–253).

### Daily scheduler job (ENRICH-05)
- `backend/app/connectors/scheduler.py` — `_scheduler_loop` (129+) with the report/snapshot/ticket 24h-gate idiom (`_last_ticket_sync` line 20, "Daily ticket status sync" ~210); add the daily EPSS/KEV refresh as an extractable, unit-testable `async def` following `_dispatch_ai_batch_prewarm` (72–107) conventions. `start_scheduler` (263) for the eager first-run wiring (D-10).

### Reference pattern for bulk backfill / re-propagation (D-01, D-10)
- `backend/app/vulnerabilities/sla_service.py` + `backend/app/vulnerabilities/router.py` — `backfill_sla_due_dates` bulk-`UPDATE … FROM` + scheduler-tick idiom (the pattern RISK-07 also cites) to mirror for the EPSS re-propagation UPDATE.

### Sibling-phase context (source-set model already shipped)
- `.planning/phases/30-correlation-schema-fix/30-CONTEXT.md` — the just-shipped `sources` ARRAY + `source_vuln_ids` JSONB correlation model and the ARRAY+GIN / per-tenant idempotent-backfill idioms; `VulnSource` enum is the 6-value source of truth.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Asset.mdm_details` (`JSONB, default=dict`, `assets/models.py:67`): direct template for `source_signals` — same sparse-JSONB shape, same "field present vs absent" semantics D-07 formalizes.
- `_upsert_vulnerability` (`sync.py:313`) is already the single choke point where every connector's `NormalizedVulnerability` becomes a row — new fields are added in exactly one place (two branches), not per-connector.
- `Vulnerability.exploit_status_id` / `exploit_status_name` (`models.py:70–71`) already demonstrate "promote a vendor-native typed signal beyond the boolean" (CrowdStrike) — `native_priority_*` extends the same idea generically.
- The scheduler's `_last_ticket_sync` 24h-gate + extractable-`async def` convention (`scheduler.py`) is the ready-made shape for the daily refresh job; `test_connector_health.py::test_scheduler_path_failure_parity` shows the unit-test convention (`from app.connectors import scheduler as scheduler_module; await scheduler_module.<fn>(...)`).
- `backfill_sla_due_dates` bulk-`UPDATE … FROM` is the shipped idiom for D-01's re-propagation and D-02's historical backfill.

### Established Patterns
- Each finding is **single-source** (`Vulnerability.source`, `models.py:62`) — this is *why* the generic `native_priority_*` pair (D-05) beats vendor-specific columns and why `source_signals` needs no vendor namespacing (the `source` column already says which vendor).
- Global-vs-tenant table split: today every table is `tenant_id`-scoped; the ref tables (D-11) are the deliberate signed-off exception (CVE-level fact).
- Feeds are external HTTP with no existing fetcher in the codebase — the daily refresh is net-new external I/O (EPSS FIRST.org, KEV CISA); atomic-swap resilience (D-09) matters because there's no other safety net on a single-VM in-process scheduler.

### Integration Points
- Alembic migration: new `epss_percentile` / `native_priority_score` / `native_priority_rating` / `source_signals` columns on `vulnerabilities` + new `epss_scores` / `cisa_kev` global tables.
- `base.py` dataclass + `sync.py` write path: additive fields threaded through both.
- `scheduler.py`: new daily refresh `async def` + eager first-run in `start_scheduler`.
- Downstream (Phase 33/34) reads these columns — this phase must land them typed and populated, not opine on their weighting.

</code_context>

<specifics>
## Specific Ideas

- SC#4 concrete fixture shape (from D-07): ingest a finding where the vendor returned `exploit_verified=false` but never returned a VPR field → assert `'vpr' not in source_signals` (missing) AND `source_signals['exploit_verified'] is False` (negative) in the same row.
- Defender is the canonical ENRICH-02 proof case: its `cisa_kev=False` hardcode (`defender.py:274`) must become authoritative-catalog-driven (D-04) — a Defender finding for a CVE in the KEV catalog must now show `cisa_kev=True`.
- Named native signals to promote into `native_priority_*` (D-05): Nessus **VPR**, CrowdStrike **ExPRT.AI** (rating + score), Qualys **QDS**, Rapid7 **Risk Score** — raw, no cross-scale mapping.

</specifics>

<deferred>
## Deferred Ideas

- **Cross-scanner normalization/weighting of native priority signals onto a common scale** → Phase 33 (Risk-Exposure Model Definition). D-05/D-06 capture raw values only; the risk model decides how VPR/ExPRT/QDS/RiskScore combine.
- **Cross-vendor `native_priority_rating` vocabulary unification** → Phase 33 (same reason — raw labels stored verbatim here).
- **Consuming these signals in a risk-exposure score / per-finding score** → Phase 33 (define, shadow) + Phase 34 (recompute + cutover).
- **Source-provenance badges & per-entity source filtering on the new/richer signals** → Phase 35.
- **Vendor/third-party ML exploit-prediction as an added signal** → RISK-11 (v2, future) — out of scope and out of milestone.

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 31-connector-enrichment-rewrite*
*Context gathered: 2026-08-05*
