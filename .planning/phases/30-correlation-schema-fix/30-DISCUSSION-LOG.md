# Phase 30: Correlation Schema Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-04
**Phase:** 30-correlation-schema-fix
**Areas discussed:** Migration strategy, Per-source vuln-id linkage, Confidence thresholds, sources array canonical form

---

## Migration strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Translate + re-correlate | Alembic translates FK→array baseline, then re-runs run_correlations per tenant to recover Qualys/Rapid7, verified with per-tenant counts | ✓ |
| Translate-only | Migration maps FK→array; Qualys/Rapid7 recovered lazily on next scheduled sync | |

**User's choice:** Translate + re-correlate
**Notes:** Correlations are derived/rebuildable from `vulnerabilities`; old FK columns never held Qualys/Rapid7 (dropped at correlation-time). Re-running is the only way to satisfy SC#2 "zero loss incl. Qualys/Rapid7" at migration time rather than after the next sync.

---

## Per-source vuln-id linkage

| Option | Description | Selected |
|--------|-------------|----------|
| Flat name array only | Store only source names; re-derive per-source finding by querying vulnerabilities | |
| Also keep source→vuln_id map | Store sources array AND a JSONB {source: vuln_id} map for direct drill | ✓ |

**User's choice:** Also keep source→vuln_id map
**Follow-up:** Confirmed shape = `source_vuln_ids` JSONB, **self-healing** — no DB FK integrity on the map; stale uuids heal on next re-correlation. (Alternative "keep 6–7 real FK columns" rejected: re-introduces the hardcoded-per-source pattern CORR-01/03 exist to kill.)

---

## Confidence thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 3/2 cutoffs | HIGH≥3, MEDIUM=2, LOW else, unchanged; defer recalibration to Phase 33 | |
| Recalibrate now | Adjust bands for the 6-source range | ✓ |

**User's choice:** Recalibrate now → **HIGH≥4 / MEDIUM 2–3 / LOW 1**
**Notes:** LOW (1) effectively unreachable since correlations require 2+ sources — intentional. Stable interim; Phase 33's risk model consumes corroboration count and may re-band. (Alternatives "HIGH≥4/MED3/LOW2" and "HIGH≥3/MED2/drop LOW" not chosen.)

---

## sources array canonical form

| Option | Description | Selected |
|--------|-------------|----------|
| Dedup + enum-order sort | Deduped VulnSource `.value` strings, sorted by enum declaration order | ✓ |
| Insertion order | Store sources as encountered during correlation | |

**User's choice:** Dedup + enum-order sort
**Notes:** Deterministic array + count; stable SC#4 regression assertion; predictable GIN `@>` containment.

---

## Claude's Discretion

- Alembic revision id/down_revision chaining, column nullability defaults, index naming (follow existing conventions).
- Whether per-tenant re-correlation runs inside the migration data step or as a separate idempotent routine (constraint: not a blocking Alembic data migration over a large table).

## Deferred Ideas

- Confidence-band re-tuning against corroboration → Phase 33.
- Source provenance badges / per-entity source filtering → Phase 35.
- DB-level referential integrity for the source→vuln_id linkage → not pursued (JSONB self-heals).
