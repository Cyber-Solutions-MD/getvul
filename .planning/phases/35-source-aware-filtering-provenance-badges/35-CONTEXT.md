# Phase 35 Context — Source-Aware Filtering & Provenance Badges

**Source:** inline discuss during "complete v4.0" (2026-08-12). FINAL phase of v4.0. Resolves the 4 research open questions.

## Domain

Honest, non-overclaiming source provenance on every finding/asset/CSPM/ticket row + real per-entity
OR/AND scanner-source filtering, built on Phase 30's `VulnerabilityCorrelation.sources` GIN ARRAY.
Requirements SRC-01..08.

## Real bug to fix (found in research)

The Assets source filter (`assets/router.py:154-159`) loops `.where(Asset.seen_by_sources.contains([s]))`
per selected scanner, which SQLAlchemy **ANDs** → multi-select today silently means "seen by ALL"
(opposite of the intended OR-default). The identical bug is in `ticketing/rule_engine.py:71-73`. Both must
become OR-default with an explicit AND toggle.

## Locked decisions

- **OR-default / AND-toggle per entity, via the correlation ARRAY operators.** Vulnerabilities + Assets:
  default OR = `&&` (array overlap / "any selected scanner"); AND toggle = `@>` (array contains / "true
  multi-scanner corroboration"). Vulnerabilities filter uses the Phase-30 `VulnerabilityCorrelation.sources`
  ARRAY (NOT the per-row `Vulnerability.source.in_()` it uses today). Assets uses `seen_by_sources`.
- **Assets partition scanner vs enrichment sources.** The Assets source filter separates scanner sources
  (CrowdStrike/Nessus/Defender/Wiz/Qualys/Rapid7) from non-scanner enrichment (JAMF/HUMAANS/Intune) — they
  are different provenance classes and must not be conflated in the filter UI or query.
- **CSPM true multi-tool AND corroboration — no silent OR.** Use a computed `GROUP BY (tenant_id, rule_id,
  resource_id)` at read time over the existing `Misconfiguration` rows (the `UniqueConstraint(tenant_id,
  rule_id, resource_id, source)` at `cspm/models.py:48` already produces one row per tool). [RESOLVED A2]
  read-time GROUP BY, NOT a new persisted correlation table / maintenance job (simpler; revisit only if
  real CSPM volume proves it too slow — document the tradeoff).
- **[RESOLVED A1] Badges reflect currently-open corroboration.** Correlation rows exist only for 2+ OPEN/
  IN_PROGRESS sources (pruned otherwise, by Phase-30 design). SourceBadgeGroup reflects the current
  correlation state; a remediated finding may show single-source. Acceptable for v1 — do NOT extend Phase-30
  status-scoped pruning to retain historical corroboration (scope creep). Document the behavior.
- **[RESOLVED A3] SourceBadgeGroup visual** follows the sketch-findings-getvul provider language (gradient
  provider marks; CISA-KEV pill precedent). Single-source = one provider mark, neutral, NO "confirmed"/
  check styling (SRC-01 non-overclaiming). Multi-source-corroborated = the group of marks + a subtle
  "N sources" count with corroboration emphasis — never the word "confirmed" from a single scanner. This is
  a reviewable design choice; follow the design system's spirit.
- **[RESOLVED A4] Ticket provenance = union of the linked vulnerability's correlation sources**, resolved
  transitively through the linked vuln. A ticket is "multi-source" if ANY linked vuln is multi-source-
  corroborated; for a grouped ticket spanning multiple CVEs, union all linked vulns' sources. Defined +
  tested (SRC-06).
- **Batching / no N+1 (SRC-08).** Extend the proven bulk-dict precedent (`risk_exposure_service.py:320-345`
  one tenant-wide select → `dict[(cve_id,asset_id)->sources]`; `ticketing/service.py:849-853` batch-all
  precedent) — one query for provenance across a page, O(1) per-row lookup. Build a query-count-assertion
  test harness from scratch (SQLAlchemy `before_cursor_execute` event-listener counter — none exists today)
  and assert no per-row N+1.
- **Frontend source list is stale — fix it.** The hardcoded `SOURCES` allow-lists (`chip-bar.tsx:26`,
  `assets-chip-bar.tsx:22`) include fake `TENABLE`/`AWS_INSPECTOR`/`MOCK` and miss real `NESSUS`/`DEFENDER`.
  Source the scanner list from the backend `VulnSource` enum (single source of truth), not a stale literal.

## Constraints (v4.0-wide)

Single-VM Docker Compose + in-process scheduler; every query tenant_id-scoped; deterministic score
authoritative. Alembic head 044_add_risk_backfill_job; revision ids ≤32 chars (a migration may not even be
needed — CSPM grouping is read-time; provenance reads existing columns).

## UI

Frontend-heavy: SourceBadgeGroup component + OR/AND source-filter chip toggle across Vulnerabilities,
Assets, CSPM, Tickets. Follow sketch-findings-getvul (provider visual language, chip-bar pattern, state
patterns, copy voice — no "confirmed" overclaim). Mandatory empty/loading/error states.
