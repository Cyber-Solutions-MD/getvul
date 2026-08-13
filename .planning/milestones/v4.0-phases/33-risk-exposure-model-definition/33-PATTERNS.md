# Phase 33: Risk-Exposure Model Definition - Pattern Map

**Mapped:** 2026-08-11
**Files analyzed:** 10 new/modified (2 new backend modules, 1 migration, 2 model edits, 1 schema edit, 1 service edit, 1 sync-hook edit, 3 centralization call-site edits, 1 frontend section edit + type edit, 2 new/extended test files)
**Analogs found:** 10 / 10 (all have a direct, read codebase analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/vulnerabilities/risk_exposure_service.py` (new) | service | batch/CRUD (pure-fn + DB-orchestration) | `backend/app/assets/risk_score.py` | role-match (per-asset aggregate vs. per-finding — same split, different math) |
| `backend/alembic/versions/042_*.py` (new migration) | migration | batch (additive schema change) | `backend/alembic/versions/035_add_enrichment_columns.py` (Vulnerability cols) + `041_add_inet_facing_signal.py` (naming/length convention) | exact (same table, same nullable-additive shape) |
| `backend/app/vulnerabilities/models.py` (edit: +3 cols) | model | CRUD | `models.py:74-79` (`native_priority_score`/`native_priority_rating`, Phase 31 precedent for "raw value, not yet normalized" doc-comment style) | exact |
| `backend/app/assets/models.py` (edit: +2 cols) | model | CRUD | `assets/models.py:62` (`risk_score: Mapped[int \| None]`) + `:105-110` (Phase 32 shadow-field doc-comment convention) | exact |
| `backend/app/connectors/sync.py` (edit: 1 line added) | route/hook (post-sync orchestration) | event-driven | `sync.py:172-173` (`compute_risk_scores` call, same block) | exact |
| `backend/app/assets/router.py` (edit: centralize 3 literals; optional new endpoint) | route/controller | request-response | `assets/router.py:650-660` (`POST /recompute-risk-scores`, admin-gated) | exact (for optional new endpoint); `router.py:297-300` (for the tier-literal edit) |
| `backend/app/assets/risk_score.py` (edit: +3 constants, RISK-06) | service/config | CRUD | `risk_score.py:44-54` (`SEVERITY_WEIGHTS` — same file, same "named module-level constant table" idiom) | exact |
| `backend/app/vulnerabilities/dashboard.py` (edit: 4 literals → constants) | controller | request-response | `dashboard.py:125-128` itself (the site being edited) | exact — pure refactor |
| `backend/app/export.py` (edit: 4 literals → constants) | controller | request-response | `export.py:368-371` itself (the site being edited) | exact — pure refactor |
| `backend/app/vulnerabilities/service.py` (edit: `get_vulnerability` +3 fields) | service | request-response | `service.py:191-231` (existing correlation lookup + `VulnerabilityResponse(...)` construction) | exact |
| `backend/app/vulnerabilities/schemas.py` (edit: +3 fields + new `RiskBreakdownComponent`) | model/schema | request-response | `schemas.py:15-52` (`VulnerabilityResponse`, same flat-optional-field convention) | exact |
| `frontend/src/lib/queries/use-vulnerability-detail.ts` (edit: +3 type fields) | hook | request-response | file itself, `VulnerabilityDetail` type (`use-vulnerability-detail.ts:12-29`) | exact |
| `frontend/src/components/vulnerabilities/drill-content.tsx` (edit: new section) | component | request-response (display) | `drill-content.tsx:611-622` (CVSS section — insertion point) + `risk-card.tsx:20-38` (`BreakdownRow`) + `RiskRing.tsx` (gauge reuse) + KEV chip `drill-content.tsx:583-586` | role-match (per-asset breakdown-row pattern reused for per-finding) |
| `backend/tests/test_risk_exposure_service.py` (new) | test | unit + integration | `backend/tests/test_correlation_service.py` (new-module test-file shape: docstring naming the Phase/requirement IDs, inline `_seed_asset`/`_seed_vuln` helpers, no prior file existed either) | role-match |
| `frontend/src/components/vulnerabilities/drill-panel.test.tsx` (extend, since no `drill-content.test.tsx` exists) | test | unit (RTL) | `drill-panel.test.tsx:1-70` (mock shape: `vi.mock('@/lib/queries/use-vulnerability-detail', ...)`, inline detail object) | exact |

## Pattern Assignments

### `backend/app/vulnerabilities/risk_exposure_service.py` (new service, batch/CRUD)

**Analog:** `backend/app/assets/risk_score.py` (147 lines)

**Module docstring / constants pattern** (`risk_score.py:1-27, 43-64`):
```python
"""Risk score computation for assets based on open vulnerabilities.
...
Per-vuln contribution:
  base weight: CRITICAL=40, HIGH=20, MEDIUM=5, LOW=1, INFO=0
  ...
"""
SEVERITY_WEIGHTS = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 5, "LOW": 1, "INFO": 0}
EXPLOIT_MULTIPLIER = 2.0
KEV_MULTIPLIER = 3.0
```
Copy: a top-of-file worked-example docstring (this project's convention for scoring modules — explains the curve/formula in prose before any code) + module-level named constants (never inline magic numbers). Apply the same for the new module's weight table (35/20/15/20/10) and `KEV_FLOOR_SCORE = 90`.

**Pure/impure split to mirror exactly** (`risk_score.py:67-81` pure, `risk_score.py:84-147` DB-orchestration):
```python
def _normalize_raw_score(raw: float) -> int:
    """Map raw weighted sum to 0-100 via piecewise curve."""
    if raw <= 0:
        return 0
    ...
    return min(int(round(score)), 100)


async def compute_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Recompute risk scores for all assets belonging to the tenant. Returns stats dict."""
    ...
    return {"assets_updated": updated}
```
Copy: the "pure fn takes primitives, returns primitives, zero DB access" / "async fn takes `(db, tenant_id)`, bulk-queries, writes, returns a stats dict" split verbatim — this is exactly what the research's `score_finding()` / `compute_finding_risk_scores(db, tenant_id)` should mirror. **What differs:** `_normalize_raw_score` is a curve-fit over an unbounded *volume* sum (many vulns per asset); the new `score_finding` is a fixed 100-point additive budget over a *single* finding's inputs — do not reuse the power/log curve math, only the pure/impure split idiom (per RESEARCH's own "Don't Hand-Roll" table).

**Bulk-fetch shape to mirror (avoid N+1)** (`risk_score.py:112-132`):
```python
raw_score_sub = (
    select(Vulnerability.asset_id, func.coalesce(func.sum(weighted_score), 0).label("raw_score"))
    .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]), Vulnerability.asset_id.isnot(None))
    .group_by(Vulnerability.asset_id)
    .subquery()
)
query = (
    select(Asset.id, func.coalesce(raw_score_sub.c.raw_score, 0).label("raw_score"))
    .outerjoin(raw_score_sub, Asset.id == raw_score_sub.c.asset_id)
    .where(Asset.tenant_id == tenant_id)
)
rows = (await db.execute(query)).all()
for asset_id, raw_score in rows:
    ...
    await db.execute(update(Asset).where(Asset.id == asset_id).values(risk_score=normalized))
```
Copy: single bulk query + Python-side loop + per-row `update()` — same shape `compute_finding_risk_scores` should use for `Vulnerability` rows, joined once to `VulnerabilityCorrelation` (by `(cve_id, asset_id)`) and once to `Asset` (for exposure fields), never a per-row correlation lookup. The correlation join itself should NOT call `get_correlation_for_vuln` per row (`correlation_service.py:170-193`, a live single-row lookup) — that function is the wrong shape here (would be N+1 across thousands of findings); instead bulk-`select` all of the tenant's `VulnerabilityCorrelation` rows once into a dict keyed by `(cve_id, asset_id)`, exactly as RESEARCH's own code-example comment (RESEARCH.md lines 295-310) specifies.

**Logging pattern** (`risk_score.py:141-145`):
```python
logger.info("risk_scores_computed", tenant_id=str(tenant_id), assets_updated=updated)
```
Copy verbatim style (structlog, snake_case event name, `tenant_id=str(...)`) for `compute_finding_risk_scores`'s own `logger.info("finding_risk_scores_computed", ...)`.

---

### `backend/alembic/versions/042_*.py` (new migration)

**Analog A (same table, additive Vulnerability columns):** `backend/alembic/versions/035_add_enrichment_columns.py`
```python
def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("epss_percentile", sa.Numeric(5, 4), nullable=True))
    op.add_column("vulnerabilities", sa.Column("native_priority_score", sa.Numeric(7, 2), nullable=True))
    op.add_column("vulnerabilities", sa.Column("native_priority_rating", sa.String(50), nullable=True))
    op.add_column("vulnerabilities", sa.Column("source_signals", postgresql.JSONB, nullable=True))
    op.create_index("ix_vulnerabilities_native_priority_score", "vulnerabilities", ["native_priority_score"])

def downgrade() -> None:
    op.drop_index(...)
    op.drop_column(...)  # reverse order of upgrade
```
Copy: nullable, no `server_default` (this is a genuinely new, unbacked-by-history column — exactly like `epss_percentile` was), JSONB via `postgresql.JSONB` for the breakdown column, plain btree index only if a future sort/filter is anticipated (RESEARCH recommends none needed yet since this is shadow-only — skip indexing `risk_exposure_breakdown`, consider indexing `Vulnerability.risk_exposure_score` only if the planner wants Phase 34 prep, otherwise omit per YAGNI). `downgrade()` drops in exact reverse order of `upgrade()`.

**Analog B (revision-id convention + docstring):** `backend/alembic/versions/041_add_inet_facing_signal.py:1-20`
```python
"""Add Asset.internet_facing_detected (Phase 32 Plan 04 — EXPO-02).
...
Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"041_add_inet_facing_signal" is 27 chars — safe.
"""
revision = "041_add_inet_facing_signal"
down_revision = "040_add_group_exposure_ovr"
```
Copy: `042_add_risk_exposure_score` (27 chars, ≤32-char constraint restated explicitly in the docstring per house convention), `down_revision = "041_add_inet_facing_signal"`. Docstring must state the char-count safety check inline (every migration in this repo since `031_rename_audit_tenant_idx.py` does this after that revision hit `StringDataRightTruncationError`).

**What differs:** this migration touches BOTH `vulnerabilities` (3 cols: `risk_exposure_score` Integer, `risk_exposure_breakdown` JSONB, `risk_model_version` String(20)) AND `assets` (2 cols: `risk_exposure_score` Integer, `risk_model_version` String(20)) in one revision — `037_add_exposure_context.py` is the closest precedent for a single migration touching only `assets` with multiple columns; no prior migration touches both tables in one revision, so order `op.add_column` calls table-by-table (vulnerabilities first, matching "finding is primary, asset is the rollup" framing) and mirror `037`'s multi-column style within each table's block.

---

### `backend/app/vulnerabilities/models.py` (edit: +3 columns on `Vulnerability`)

**Analog:** `models.py:74-79` (`native_priority_score`/`native_priority_rating`, the most recent "phase says X, this column intentionally does not do X yet" doc-comment)
```python
# ENRICH-03/D-05 (Phase 31 Plan 01): generic vendor-native composite pair --
# raw value/label verbatim, no cross-scale normalization (that's Phase 33).
# Nullable: 2 of 6 connectors (Defender, Wiz) have no vendor-authored
# composite and leave these explicitly None (31-RESEARCH.md Pitfall 6).
native_priority_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
native_priority_rating: Mapped[str | None] = mapped_column(String(50))
```
Copy: the doc-comment convention that names the Phase/Plan and explicitly cross-references the NEXT phase that resolves the noted gap — invert it for Phase 33's new columns (cite RISK-01/02/06, note these ARE the normalized/persisted score this comment above literally promised). Add directly below `source_signals` (`models.py:86`), same style:
```python
# RISK-01/02/06 (Phase 33): the normalized per-finding score this file's
# own native_priority_score comment (above) promised. Shadow-computed only
# — see risk_exposure_service.py. Nullable until first post-Phase-33 sync.
risk_exposure_score: Mapped[int | None] = mapped_column(Integer)
risk_exposure_breakdown: Mapped[dict | None] = mapped_column(JSONB)
risk_model_version: Mapped[str | None] = mapped_column(String(20))
```
**What differs:** no `server_default` (unlike Phase 32's exposure columns at `assets/models.py:105-110`, which back-filled every row with `MEDIUM`/`AUTO` immediately) — these three are genuinely `NULL` until the first post-migration sync runs `compute_finding_risk_scores`, exactly like `internet_facing_detected` (`assets/models.py:119`, "nullable, no server_default... None until a vendor signal arrives" — swap "vendor signal" for "first shadow-compute pass").

---

### `backend/app/assets/models.py` (edit: +2 columns on `Asset`, shadow rollup)

**Analog:** `assets/models.py:62` (`risk_score: Mapped[int | None] = mapped_column(Integer)`) + the Phase-32 doc-comment block at `:96-104`.

**What to copy:** bare `Integer` column, no discriminator/source column (RISK-02's rollup is a pure derived MAX, not user-editable, so it needs no `*_source` field unlike `business_criticality_source` etc.). Add directly after `risk_score` (`:62`):
```python
# RISK-02 (Phase 33): shadow rollup, NOT the live Asset.risk_score above.
# MAX(risk_exposure_score) across the asset's OPEN/IN_PROGRESS findings —
# a separate, additive column so risk_score.py's live curve is untouched.
# Phase 34 owns any cutover of consumers to this value.
risk_exposure_score: Mapped[int | None] = mapped_column(Integer)
risk_model_version: Mapped[str | None] = mapped_column(String(20))
```
**What differs from the Vulnerability-side columns:** no `risk_exposure_breakdown` JSONB on `Asset` (RISK-02 only asks for a rollup number; the per-input breakdown is per-finding only, surfaced in the DrillPanel for one finding at a time — an asset-level breakdown was never asked for and would require re-deriving "which finding's breakdown wins," which is exactly the MAX-rollup ambiguity flagged as Open Question 2/Assumption A4 in RESEARCH — do not build it).

---

### `backend/app/connectors/sync.py` (edit: +1 call, post-sync hook)

**Analog:** `sync.py:16` (import) + `sync.py:171-173` (the exact call site)
```python
from app.assets.risk_score import compute_risk_scores
...
# Post-sync: run correlation engine and risk score computation
corr_stats = await run_correlations(db, connector_config.tenant_id)
risk_stats = await compute_risk_scores(db, connector_config.tenant_id)
```
Copy exactly: add `from app.vulnerabilities.risk_exposure_service import compute_finding_risk_scores` alongside the existing import block (`sync.py:14-20` area), then one new line immediately after `risk_stats = ...`:
```python
finding_risk_stats = await compute_finding_risk_scores(db, connector_config.tenant_id)
```
and add `"finding_risk_scores": finding_risk_stats` to the `log.details` dict (`sync.py:178-186`), mirroring how `"risk_scores": risk_stats` is already threaded through. **What differs:** this is the ONLY call site to wire in Phase 33 (CONTEXT.md RESOLVED Q1) — do NOT touch the ~9 other `compute_risk_scores` call sites (`vulnerabilities/router.py` lines ~508/523/544/557/576/609/745/770/804/818, `ticketing/router.py:463`, `seed.py:242`, `dev_routes.py:35`) even though they exist and are tempting to "keep consistent." Leave them untouched — Phase 34 decides if the new function needs that same fan-out.

---

### `backend/app/assets/router.py` (edit: centralize tier literals; optional new endpoint)

**Tier-literal edit — analog is the exact site itself** (`assets/router.py:297-300`):
```python
risk_q = select(
    func.count().filter(Asset.risk_score >= 80).label("critical"),
    func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)).label("high"),
    func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)).label("medium"),
    func.count().filter(Asset.risk_score < 20).label("low"),
).where(...)
```
Replace `80`/`50`/`20` with `RISK_SCORE_TIER_CRITICAL`/`RISK_SCORE_TIER_HIGH`/`RISK_SCORE_TIER_MEDIUM` imported `from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM`. Zero behavior change — same exact boolean expressions, just named constants substituted for literals.

**Optional new admin recompute endpoint — analog** (`assets/router.py:650-660`):
```python
@router.post("/recompute-risk-scores")
async def recompute_risk_scores(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Recompute risk scores for all assets based on current vulnerabilities."""
    from app.assets.risk_score import compute_risk_scores
    stats = await compute_risk_scores(db, user.tenant_id)
    await db.commit()
    return {"message": "Risk scores recomputed", **stats}
```
Note the immediate neighbor at `:663-670`, `POST /exposure-context/recompute`, whose own docstring says "Mirrors `POST /assets/recompute-risk-scores`" — establishing this repo's convention of literally copying the prior admin-recompute endpoint shape for each new full-tenant-recompute feature. **This endpoint is NOT required by RISK-01..06** (CONTEXT.md/RESEARCH's Open Question 1 resolves that the sync-hook alone satisfies "shadow-computed for one full cycle") — it is Claude's Discretion whether the planner adds `POST /vulnerabilities/recompute-risk-exposure` (or similar) as a manual-trigger convenience mirroring this exact pattern, in `vulnerabilities/router.py` not `assets/router.py` (since the new function lives in the vulnerabilities package). If added, it MUST call `audit(db, user, "vulnerability.recompute_risk_exposure", ...)` before `db.commit()` (see Shared Patterns below) since v4.0's own constraint says "audit new mutating admin actions" — note the EXISTING `/recompute-risk-scores` endpoint above does NOT call `audit()`, so a literal copy would silently violate the v4.0-wide constraint; the new endpoint must add the audit call, deviating from this analog on that one point.

---

### `backend/app/assets/risk_score.py` (edit: +3 constants, RISK-06 centralization)

**Analog:** the file's own existing constant-table idiom (`risk_score.py:43-54`):
```python
SEVERITY_WEIGHTS = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 5, "LOW": 1, "INFO": 0}
EXPLOIT_MULTIPLIER = 2.0
KEV_MULTIPLIER = 3.0
```
Add, same module, same style, near the top:
```python
# RISK-06 (Phase 33): centralizes the >=80/>=50/>=20 tier boundaries
# previously triplicated at dashboard.py:125-128, export.py:368-371,
# assets/router.py:297-300. Pure refactor — zero behavior change.
RISK_SCORE_TIER_CRITICAL = 80
RISK_SCORE_TIER_HIGH = 50
RISK_SCORE_TIER_MEDIUM = 20
```
This file is correctly identified as the constants' new home because it already owns `SEVERITY_WEIGHTS` for the very `Asset.risk_score` column these boundaries bucket (RESEARCH's own reasoning, confirmed by direct read — do not create a new `constants.py` module for 3 integers).

---

### `backend/app/vulnerabilities/dashboard.py` / `backend/app/export.py` (edit: import + literal→constant swap)

**Both analogs are the exact sites being edited** (`dashboard.py:125-128`, `export.py:368-371`) — confirmed byte-for-byte identical four-way boolean split at both locations (plus `assets/router.py:297-300` above). Add `from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM` to each file's import block; substitute literals. **Regression-test gap:** confirmed via grep — no existing test (`test_dashboard_tiles.py` covers `/dashboard/tiles` and `/dashboard/nav-counts`, NOT `get_overview_stats`'s `risk_distribution` block at `dashboard.py:118-128`, nor `export.py`'s). Add/extend a regression test asserting identical bucket counts before/after the refactor — this is a genuinely new test surface for this specific endpoint output, not an extension of `test_dashboard_tiles.py`'s existing 5 tests (they test different response shapes).

---

### `backend/app/vulnerabilities/service.py` (edit: `get_vulnerability` +3 fields)

**Analog:** `service.py:172-231` (the exact function being edited), specifically the existing correlation lookup + explicit-kwargs response construction:
```python
corr_count = None
if vuln.cve_id and vuln.asset_id:
    corr_q = select(VulnerabilityCorrelation.sources_count).where(
        VulnerabilityCorrelation.tenant_id == tenant_id,
        VulnerabilityCorrelation.cve_id == vuln.cve_id,
        VulnerabilityCorrelation.asset_id == vuln.asset_id,
    )
    corr_result = (await db.execute(corr_q)).scalar_one_or_none()
    corr_count = corr_result

return VulnerabilityResponse(
    id=vuln.id, ...,
    correlation_sources_count=corr_count,
)
```
**What to copy:** the explicit-kwargs `VulnerabilityResponse(...)` construction style — every field is named, nothing is passed via `**vuln.__dict__` or similar shortcut. Add `risk_exposure_score=vuln.risk_exposure_score, risk_exposure_breakdown=vuln.risk_exposure_breakdown, risk_model_version=vuln.risk_model_version` as three more explicit kwargs.
**What differs (Pitfall 4 from RESEARCH, load-bearing):** do NOT add a new live per-request lookup/recompute block mirroring the `corr_count` pattern above — these three new fields are already-selected columns on the `vuln` ORM object already fetched by the query at `service.py:176-181` (`select(Vulnerability)...`), so reference them directly (`vuln.risk_exposure_score`), zero new query. Copy the *kwargs-passing* idiom from this function, but explicitly do NOT copy the *live-lookup* idiom for these particular fields — the persisted-column read is correct here, the live lookup is the anti-pattern to avoid (RESEARCH Pitfall 4).

---

### `backend/app/vulnerabilities/schemas.py` (edit: +3 fields + new `RiskBreakdownComponent`)

**Analog:** `schemas.py:15-46` (`VulnerabilityResponse`'s existing optional-field tail):
```python
epss_percentile: Decimal | None = None
native_priority_score: Decimal | None = None
native_priority_rating: str | None = None
source_signals: dict[str, Any] | None = None
```
Copy this exact flat-optional-with-default-None convention (not nested, not `Field(...)`-wrapped unless an existing field nearby uses `Field`) for:
```python
risk_exposure_score: int | None = None
risk_exposure_breakdown: list[RiskBreakdownComponent] | None = None
risk_model_version: str | None = None
```
New `RiskBreakdownComponent(BaseModel)` (fields per RESEARCH: `key`, `label`, `raw_value: str`, `points: float`, `max_points: float`) belongs in the same file, defined ABOVE `VulnerabilityResponse` (matching this file's top-to-bottom convention of defining nested/referenced schemas before the schema that uses them — confirm by checking if any other nested schema exists above `VulnerabilityResponse` in the file; if none does yet, this establishes the pattern others already implicitly follow via ordering).

---

### `frontend/src/lib/queries/use-vulnerability-detail.ts` (edit: +3 type fields)

**Analog:** the file itself, `VulnerabilityDetail` type (`:12-29`) — flat, no nesting beyond arrays:
```typescript
export type VulnerabilityDetail = {
  id: string;
  cve_id: string | null;
  ...
  status: string;
  first_detected_at: string;
  last_seen_at: string;
};
```
Add at the end, same flat style:
```typescript
risk_exposure_score: number | null;
risk_exposure_breakdown: RiskBreakdownComponent[] | null;
risk_model_version: string | null;
```
with a new exported `RiskBreakdownComponent` type (mirroring the backend schema shape 1:1 — `key`, `label`, `raw_value`, `points`, `max_points`). No change needed to the `useQuery`/`api<VulnerabilityDetail>(...)` call itself — same endpoint, response just grows 3 fields, matching how `cisa_kev`/`exploit_available` etc. were presumably added incrementally to this same flat type over prior phases.

---

### `frontend/src/components/vulnerabilities/drill-content.tsx` (edit: new "Risk Exposure" section)

**Insertion point analog:** `drill-content.tsx:611-622` (CVSS section, ends right before `<section aria-labelledby="drill-hosts-h">` at line 624):
```tsx
<section aria-labelledby="drill-cvss-h">
  <h4 id="drill-cvss-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
    {microcopy.drill.sections.cvss}
  </h4>
  <div className="font-mono text-sm text-text">
    Score: {v.cvss_v3_score?.toFixed(1) ?? '—'} · Vector: {v.cvss_v3_vector ?? '—'}
  </div>
</section>
```
Copy: the `<section aria-labelledby="drill-risk-exposure-h">` wrapper shape, `<h4 id="..." className="mb-2 text-xs uppercase tracking-wide text-text-muted">` heading convention, sourcing the label text from `microcopy.drill.sections.*` (new key needed there, not a hardcoded string — per CLAUDE.md copy-voice rule). Insert this new section directly AFTER the CVSS section and BEFORE "Affected hosts" (per RESEARCH's explicit ordering rationale: "the analyst reads the raw CVSS number, then immediately sees why it scored an 82").

**Breakdown-row composition analog:** `frontend/src/components/assets/risk-card.tsx:20-38` (`BreakdownRow` + its usage) + `frontend/src/components/ui/RiskRing.tsx` (gauge):
```tsx
function BreakdownRow({ count, label, tintClass, testId }: {...}) {
  return (
    <div className="flex items-center justify-between border-t border-border-subtle py-2 text-sm" data-testid={testId}>
      <span className="text-text-muted">{label}</span>
      <span className={cn('font-mono tabular-nums', tintClass)}>{count}</span>
    </div>
  );
}
...
<RiskRing score={asset.risk_score} />
```
Copy: this exact `label` (left) / tinted `font-mono tabular-nums` value (right) row shape for each of the ~7 `RiskBreakdownComponent` rows (render `${raw_value} → ${points}/${max_points} pts` as the right-hand value). Reuse `RiskRing` at a smaller `size` prop next to the section heading for the overall `risk_exposure_score` badge — do NOT build a second gauge component. **What differs:** `RiskCard`'s 4 rows are FIXED/named (Critical/SLA/KEV/Trend); the new section's rows are DATA-DRIVEN (`.map()` over the `risk_exposure_breakdown` array returned by the API) since the exact component list and point values are server-computed, not client-hardcoded.

**KEV-floor chip analog:** `drill-content.tsx:583-586` (existing "★ CISA KEV" chip):
```tsx
{v.cisa_kev && (
  <span className="rounded-md bg-pink-soft px-2 py-0.5 font-mono text-[10px] font-medium uppercase text-[var(--color-severity-critical-on-soft)]">
    ★ CISA KEV
  </span>
)}
```
Copy the exact class list for a new "★ KEV floor applied" chip inside the new section (not the header), conditioned on `v.cisa_kev && <subtotal below floor, i.e. the floor actually changed the outcome>` — the breakdown response should either include a `kev_floor_applied: boolean` field or the frontend can infer it from `risk_exposure_breakdown` summing to less than `risk_exposure_score` when `cisa_kev` is true (prefer the explicit boolean from the backend — cheaper and unambiguous, avoid frontend re-deriving business logic).

**Explicitly NOT the pattern to copy:** `frontend/src/components/ai/ai-explanation-citations.tsx` (per-text-segment tooltip citations for AI prose provenance) — wrong shape for a fixed `{label, raw_value, points, max_points}` row list; do not force-fit tooltips onto this section (RESEARCH's own explicit call-out).

**Shadow/preview caption:** no existing exact analog for a "Preview — not yet used for sorting or alerts" caption; nearest precedent for small italicized/muted meta-captions under a section heading is `RiskRing.tsx`'s own `caption` prop rendering (`'Risk unavailable'` / `'No exposures'`, styled `mt-1 text-xs text-text-faint`). Reuse that exact `text-xs text-text-faint` styling for the new caption. Must go through `microcopy.ts`, not be hardcoded inline (copy-voice rule) — no "Coming soon!" boilerplate per CLAUDE.md.

---

### `backend/tests/test_risk_exposure_service.py` (new)

**Analog:** `backend/tests/test_correlation_service.py` (new-module test file, no prior coverage existed either) — docstring convention:
```python
"""Phase 30 Plan 01 — SC#4 regression coverage for correlation_service.py
(CORR-01/CORR-03).

Behaviour under test (D-10): ...
"""
```
Copy: name the Phase + requirement IDs in the module docstring, state explicitly "no prior test file existed" if true (confirmed true here — zero grep hits for any `risk_exposure_service` test). Fixture style: RESEARCH's own fixture code (KEV floor `FindingScoreInputs`/`replace()`, corroboration `sources_count=1` vs `3`) is directly usable — `dataclasses.replace` on an immutable input dataclass, not a fresh object literal per test, mirrors nothing existing verbatim but is idiomatic pytest and should be adopted as specified in 33-RESEARCH.md's own code blocks (KEV Floor Mechanics / Corroboration Mechanics sections) rather than re-invented.
**DB-fixture seeding style** — mirror `test_correlation_service.py`'s `_seed_asset`/`_seed_vuln` inline helpers (not a shared conftest fixture) for `compute_finding_risk_scores`'s integration-level test.

---

### `frontend/src/components/vulnerabilities/drill-panel.test.tsx` (extend — no `drill-content.test.tsx` exists)

**Analog:** the file itself, `:1-70` — mock shape:
```tsx
vi.mock('@/lib/queries/use-vulnerability-detail', () => ({
  useVulnerabilityDetail: vi.fn(),
}));
import { useVulnerabilityDetail } from '@/lib/queries/use-vulnerability-detail';
```
Copy: add new test cases to THIS file (not a new `drill-content.test.tsx` — none exists; `DrillContent` is exercised only via `DrillPanel`/`DrillPanelMobile` wrapper tests per the codebase's existing convention, confirmed via `find` — only `drill-panel.test.tsx` and `drill-panel-mobile.test.tsx` exist, no bare `drill-content.test.tsx`). Extend the existing inline mock detail object with `risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version`, then assert the new section renders (`screen.getByText(...)` or `data-testid` per the file's existing query style).

## Shared Patterns

### Audit trail for new mutating admin actions
**Source:** `backend/app/audit.py:136-` (`audit(db, user, action, resource_type, resource_id, details)`), called BEFORE `db.commit()` per `assets/router.py:645` (`await audit(...); await db.commit()`).
**Apply to:** ONLY if the planner adds a new admin recompute endpoint for the finding-level score (optional, Claude's Discretion — not required by RISK-01..06). The existing `/assets/recompute-risk-scores` endpoint does NOT call `audit()` — do not copy that omission; v4.0's constraints explicitly require auditing new mutating admin actions.

### Tenant scoping
**Source:** every query in `risk_score.py` (`.where(Asset.tenant_id == tenant_id)` / `Vulnerability.tenant_id == tenant_id`), `correlation_service.py:118`.
**Apply to:** every new query in `risk_exposure_service.py` — no new pattern, just consistent application of the existing one (per RESEARCH's Security Domain section, V4 Access Control).

### Structlog event logging
**Source:** `risk_score.py:141-145` (`logger.info("risk_scores_computed", tenant_id=str(tenant_id), assets_updated=updated)`).
**Apply to:** `compute_finding_risk_scores`'s own `logger.info("finding_risk_scores_computed", tenant_id=str(tenant_id), findings_updated=..., assets_rolled_up=...)`.

### Doc-comment convention for shadow/deferred columns
**Source:** `assets/models.py:96-104` (Phase-32 exposure-context block), `assets/models.py:119` (`internet_facing_detected`), `vulnerabilities/models.py:74-77` (`native_priority_score`).
**Apply to:** every new column added in this phase — cite the Phase/requirement ID, state explicitly what does NOT happen yet (no consumer reads it, no backfill), and cross-reference which future phase resolves it.

### Copy-voice / microcopy.ts sourcing
**Source:** `drill-content.tsx` uses `microcopy.drill.sections.cvss` etc. rather than inline strings, throughout the file.
**Apply to:** every new label in the DrillPanel's Risk Exposure section (section heading, "Preview" caption, "KEV floor applied" chip text) must be added to `microcopy.ts`, not hardcoded.

## No Analog Found

None — every file/change in this phase has a direct, recently-modified, read codebase analog (this phase is explicitly designed to be additive-only against Phases 30-32's already-landed inputs).

## Anti-Patterns to Avoid

| Anti-pattern | Why it's wrong | Correct pattern |
|---|---|---|
| Editing/touching `backend/app/assets/service.py` or `backend/app/assets/schemas.py` | Both files are dead code — confirmed via grep, zero imports from either anywhere in `app/` outside themselves (136 and 76 lines respectively, containing stale `risk_score` references from before the current `assets/router.py`-direct pattern took over) | Ignore entirely; all live asset endpoints are in `assets/router.py` directly |
| Reusing `risk_score.py`'s power/log curve (`_normalize_raw_score`) for the new per-finding score | That curve exists specifically to tame *volume* of vulns on one asset; a single finding has no volume dimension | Fixed 100-point additive weighted-sum, no curve-fitting |
| Wiring `compute_finding_risk_scores` into any of the ~9 other `compute_risk_scores` call sites (`vulnerabilities/router.py`, `ticketing/router.py:463`, `seed.py:242`, `dev_routes.py:35`) | CONTEXT.md RESOLVED Q1 — only the `sync.py:172-173` hook this phase | Single hook point; staleness until next sync is acceptable for a shadow value |
| Making `get_vulnerability` recompute `score_finding` live on every GET (mirroring the `corr_count` live-lookup pattern at `service.py:191-200`) | RESEARCH Pitfall 4 — would let the DrillPanel show a value that can drift from what a future bulk consumer reads from the persisted column | Read the persisted `risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version` columns directly off the already-fetched `vuln` ORM object, zero new query |
| Implementing the KEV floor as `subtotal + KEV_BONUS` (additive) | Could push above 100 needing an extra clamp; doesn't match "floor" semantics or make the fixture trivially exact | `final_score = max(subtotal, KEV_FLOOR_SCORE) if cisa_kev else subtotal` |
| Trusting CrowdStrike's numeric `native_priority_score` (`exprt_score`) for normalization | Field name AND scale both unverified (`crowdstrike.py:378-391`) — Phase 31's own flagged risk, compounding it here would be new, avoidable risk | Use `native_priority_rating` (confirmed categorical field) for CrowdStrike only |
| Adding a 4th copy of `>=80/>=50/>=20` anywhere, or touching `frontend/src/components/ui/RiskRing.tsx:22-25`'s `getRiskBand()` | RiskRing.tsx is explicitly out of scope this phase (CONTEXT.md: "the 4th copy in frontend RiskRing.tsx is out of scope this phase — note it") | Only the 3 backend files (`dashboard.py`, `export.py`, `assets/router.py`) import from the new `app.assets.risk_score` constants |
| Wiring the new score into ANY automated consumer this phase — SLA breach detection, list default-sort, `sort="triage"`, trend charts, `min_risk_score` automation-rule conditions, the AI batch selector (`get_top_findings_for_ai_batch`) | RISK-06 zero-consumer gate; explicitly Phase 34 (RISK-08) scope | The only reader in Phase 33 is the DrillPanel's read-only display — grep-provable: `grep -rn "risk_exposure_score\|risk_exposure_breakdown" backend/app --include="*.py" \| grep -v risk_exposure_service.py` should show only `models.py`, `schemas.py`, `service.py` (the read for display), and the 042 migration |
| Building a volume-sensitive curve for the `Asset.risk_exposure_score` rollup | CONTEXT.md RESOLVED Q2 — MAX only, this phase; a curve is explicitly deferred to Phase 34 | `Asset.risk_exposure_score = MAX(risk_exposure_score)` across the asset's OPEN/IN_PROGRESS findings |
| Renormalizing weights when an input is missing (e.g., "average only the signals we have") | RESEARCH Pitfall 5 — produces misleadingly high scores from sparse samples | Missing signal contributes exactly 0 points out of its fixed budget, never renormalized |
| Creating a new bare `drill-content.test.tsx` file | No such file exists in the codebase's actual test layout — `DrillContent` is only tested via its `DrillPanel`/`DrillPanelMobile` wrappers | Extend `drill-panel.test.tsx` (and/or `drill-panel-mobile.test.tsx` if a mobile-specific assertion is warranted) |

## Metadata

**Analog search scope:** `backend/app/assets/`, `backend/app/vulnerabilities/`, `backend/app/connectors/sync.py`, `backend/app/export.py`, `backend/alembic/versions/` (last 8 revisions), `backend/tests/` (correlation/exposure/dashboard test files), `frontend/src/components/vulnerabilities/`, `frontend/src/components/assets/`, `frontend/src/components/ui/RiskRing.tsx`, `frontend/src/lib/queries/use-vulnerability-detail.ts`
**Files scanned:** ~25 read directly (file:line cited above), plus grep sweeps across `backend/app/`, `backend/tests/`, `frontend/src/`
**Pattern extraction date:** 2026-08-11
