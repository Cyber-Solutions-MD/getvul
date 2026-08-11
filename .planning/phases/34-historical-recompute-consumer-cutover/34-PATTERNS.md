# Phase 34: Historical Recompute & Consumer Cutover - Pattern Map

**Mapped:** 2026-08-11
**Files analyzed:** 14 new/modified backend files (no frontend files this phase — flag stays OFF, no UI wired)
**Analogs found:** 14 / 14 (every file has at least a role-match; several have exact analogs)

This phase is pure synthesis, not invention — every mechanism (durable job state, gated scheduler
dispatch, bulk `UPDATE...FROM`, per-tenant boolean flag, admin-gated + audited mutation endpoint,
dead-code fix + dual-write) already exists somewhere in this codebase, per 34-RESEARCH.md. This map
tells the planner/executors exactly which existing file to open side-by-side with each new/modified file.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/vulnerabilities/models.py` (+`RiskExposureBackfillJob`) | model | batch/durable-job-state | `app/ai/models.py:52-90` (`AiBatchJob`) | exact (shape), needs new resume-cursor field |
| `app/vulnerabilities/risk_backfill_service.py` (NEW file) | service | batch/chunked-CRUD | `app/vulnerabilities/risk_exposure_service.py:313-426` (`compute_finding_risk_scores`) + `sla_service.py:41-61` (`backfill_sla_due_dates`) + `enrichment_feeds.py:234-262` (`repropagate_enrichment`) | role-match (synthesis of 3) |
| `app/connectors/scheduler.py` (+`_dispatch_risk_exposure_backfill`) | service (dispatcher) | event-driven/scheduler-tick | `scheduler.py:73-107` (`_dispatch_ai_batch_prewarm`, create_task shape) + `scheduler.py:130-204` (`_dispatch_enrichment_refresh`, lock/gate shape) | exact (synthesis of 2) |
| `alembic/versions/044_add_risk_backfill_job.py` (NEW) | migration | schema | `alembic/versions/038_add_exposure_cal_cfg.py` (flag column) + `042_add_risk_exposure_score.py` (nullable additive columns) | exact |
| `app/tenants/models.py` (+3 columns) | model | CRUD (config) | `app/tenants/models.py:46-52` (`exposure_hard_cap_enabled` + comment block) | exact |
| `app/vulnerabilities/service.py:92-99` (`sort="triage"`, MODIFIED) | service (query-builder) | request-response | itself — existing `filters.sort ==` chain (`service.py:92-143`); Tenant-fetch precedent `sla_service.py:43` | exact |
| `app/vulnerabilities/service.py:534-579` (`get_top_findings_for_ai_batch`, MODIFIED) | service (query-builder) | request-response | itself + `sla_service.py:43` (Tenant fetch) | exact |
| `app/vulnerabilities/risk_cutover_service.py` (NEW file — diff+ack) | service | CRUD/transform (report) | `rule_engine.py:65-67` (`min_risk_score` read) + `saved_filters.py:104-105` (same, JSONB) | role-match |
| `app/vulnerabilities/router.py` or `app/assets/router.py` (+2 admin endpoints: flag-flip, threshold-diff) | route (admin, RBAC+audited) | request-response | `assets/router.py:655-665` (`POST /assets/recompute-risk-scores`, `require_role("admin")`) + `:650` (`audit()` call before commit) | exact |
| `app/vulnerabilities/trends.py:306-318` (`capture_daily_snapshot`, MODIFIED — dual-write) | service (batch/transform) | batch | itself — existing `avg_risk` block (`trends.py:278-285`) | exact |
| `app/notifications/alerts.py:189-255` (`_check_risk_score_changes`, MODIFIED — bug fix + guard) | service (event-driven check) | event-driven | itself + `alerts.py:100-141` (`_check_sla_breaches`, sibling per-tenant check shape) | exact |
| `backend/tests/test_risk_exposure_backfill.py` (NEW) | test | batch/event-driven | `tests/test_scheduler_ai_batch.py` (dispatcher+monkeypatch) + `tests/test_scheduler_enrichment_refresh.py` (24h-gate dispatch) + `tests/test_risk_exposure_service.py:149-204` (fixture-seed pattern) | role-match (synthesis) |
| `backend/tests/test_risk_cutover_ack.py` (NEW) | test | request-response | `tests/test_asset_exposure.py:354-425` (admin-RBAC + audit-row test pattern) + `tests/test_rule_engine.py:98-103` (`min_risk_score` fixture pattern) | role-match |
| `backend/tests/test_severity_trends.py` (EXTEND) + `backend/tests/test_risk_score_change_alerts.py` (NEW) | test | batch/event-driven | itself (`test_severity_trends.py`) for the snapshot-fixture idiom; **no existing analog** for the alerts-check test — flagged below | partial / no-analog |

## Pattern Assignments

### `app/vulnerabilities/models.py` — new `RiskExposureBackfillJob` (job model)

**Analog:** `app/ai/models.py:52-90` (`AiBatchJob`)

**Class shape to copy** (`app/ai/models.py:52-90`):
```python
class AiBatchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_batch_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anthropic_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")  # in_progress|completed
    ...
```
Copy: `Base, UUIDPrimaryKeyMixin, TimestampMixin` base classes, the `tenant_id` FK-with-CASCADE-and-index column
(identical on every tenant-scoped table in this codebase), the plain `String(20)` status-enum-as-string idiom
(no Python `enum.Enum` used for job status anywhere in this codebase — don't introduce one here either).

**What differs:** `RiskExposureBackfillJob` needs a `UniqueConstraint("tenant_id", ...)` (one row per tenant
ever — `AiBatchJob` has no such constraint because it's one row per submitted batch, many per tenant) PLUS a
`cursor_vuln_id` keyset-resume column `AiBatchJob` doesn't need (a Message Batch delegates state to Anthropic;
this job chunks within Postgres itself). Add `rows_migrated`, `rows_total_estimate`, `chunk_size`,
`last_heartbeat_at`, `error_message` per 34-RESEARCH.md's exact schema (lines 169-183). Place the class in
`app/vulnerabilities/models.py` (next to `Vulnerability`/`VulnerabilityCorrelation`/`EpssScore`/`CisaKev` —
domain-file convention, not a dedicated `app/vulnerabilities/risk_backfill_models.py`, since this codebase
puts ALL of a domain's tables in one `models.py`, e.g. `app/vulnerabilities/models.py` already holds 4 unrelated-shaped tables).

---

### `app/vulnerabilities/risk_backfill_service.py` (NEW) — chunked resumable backfill

**Analogs (3, synthesized):**

1. **Row-scoring reuse** — `app/vulnerabilities/risk_exposure_service.py:313-426` (`compute_finding_risk_scores`):
```python
# Source: risk_exposure_service.py:336-345 — bulk correlation pre-fetch, avoid N+1
corr_rows = (await db.execute(
    select(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id, VulnerabilityCorrelation.sources_count)
    .where(VulnerabilityCorrelation.tenant_id == tenant_id)
)).all()
corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}
```
Reuse `score_finding(FindingScoreInputs) -> RiskBreakdown` (`risk_exposure_service.py:141-310`) verbatim — do
NOT write a second scoring function (Don't-Hand-Roll table, RESEARCH.md line 324). Import `RISK_MODEL_VERSION`
(`risk_exposure_service.py:90`, `= "v1"`) as the idempotency-guard version stamp.

2. **Idempotent WHERE-guard shape** — `app/vulnerabilities/sla_service.py:41-61` (`backfill_sla_due_dates`):
```python
result = await db.execute(
    update(Vulnerability)
    .where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.severity == severity,
        Vulnerability.sla_due_at.is_(None),   # <- the idempotency guard idiom to copy
        ...
    )
    .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
)
updated += result.rowcount
```
Copy the **shape** (`WHERE <not-yet-migrated>` makes re-runs cheap/safe) — do **not** copy this function's
lack of chunking (Pitfall 1, RESEARCH.md line 332-335). The backfill's guard is
`Vulnerability.risk_model_version.is_(None) | (Vulnerability.risk_model_version != RISK_MODEL_VERSION)`.

3. **Bulk `UPDATE...FROM` shape** — `app/connectors/enrichment_feeds.py:251-256` (`repropagate_enrichment`), the
ONLY existing `UPDATE...FROM` in the codebase:
```python
epss_result = await db.execute(
    text(
        "UPDATE vulnerabilities v SET epss_score = e.epss_score, "
        "epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id"
    )
)
```
Adapt this SQL *shape* (`UPDATE t SET ... FROM (subquery/VALUES) WHERE join`) — but scope it per-tenant and
chunked (this existing one is global + unchunked; the backfill needs the opposite on both axes).

**Claim-a-chunk concurrency guard** (new pattern — no exact precedent, closest is `_enrichment_refresh_lock`'s
in-memory `asyncio.Lock()` at `scheduler.py:130`, explicitly NOT reusable per RESEARCH.md's Don't-Hand-Roll
table since an in-memory lock doesn't survive a restart): use a single `UPDATE ... WHERE status IN (...) AND
stale_heartbeat RETURNING id` claim statement (RESEARCH.md lines 192-206) — this is genuinely new SQL in this
codebase but composed from primitives (`UPDATE...RETURNING` is standard SQLAlchemy Core, no new library).

**Per-tenant/per-job isolation** — mirror `app/ai/batch.py:373-395` (`poll_pending_batches`)'s per-job
try/except + re-select-by-ID-not-ORM-reference idiom:
```python
# Source: app/ai/batch.py:375-381
job_ids = (await db.execute(select(AiBatchJob.id).where(AiBatchJob.status == "in_progress"))).scalars().all()
for job_id in job_ids:
    try:
        job = (await db.execute(select(AiBatchJob).where(AiBatchJob.id == job_id))).scalar_one_or_none()
        if job is None:
            continue  # completed/removed concurrently -- nothing to do
```
Copy this exact idiom for the backfill's per-tenant loop: select `tenant_id`s (not `Tenant` ORM refs) up front,
re-fetch each tenant's job row fresh inside its own try/except, because a `db.rollback()` recovering from one
tenant's failure expires the whole session's identity map (documented hazard at `batch.py:357-367`).

---

### `app/connectors/scheduler.py` — new `_dispatch_risk_exposure_backfill`

**Analog 1 (dispatch idiom — `asyncio.create_task`, never inline):** `scheduler.py:73-107` (`_dispatch_ai_batch_prewarm`):
```python
# Source: scheduler.py:97-106
global _last_ai_batch_prewarm
try:
    now = datetime.now(UTC)
    if _last_ai_batch_prewarm is None or (now - _last_ai_batch_prewarm).total_seconds() >= 86400:
        from app.ai.batch import run_batch_prewarm
        asyncio.create_task(run_batch_prewarm())
        _last_ai_batch_prewarm = now
except Exception as e:
    logger.error("ai_batch_prewarm_dispatch_error", error=str(e))
```
Copy: top-level function (not inlined in `_scheduler_loop()`, so it's directly unit-testable via
`from app.connectors import scheduler as scheduler_module; await scheduler_module._dispatch_risk_exposure_backfill()`
— exact convention cited in `test_scheduler_ai_batch.py`/`test_scheduler_enrichment_refresh.py` docstrings),
`asyncio.create_task` (never inline `await`, since — like the AI batch prewarm and UNLIKE the enrichment
refresh — the backfill's chunk is NOT a single atomic all-or-nothing unit; partial progress is the point),
try/except-wraps-everything + `logger.error(...)` log-and-continue.

**What differs:** no in-memory `_last_*` gate at all — the gate is the durable per-tenant claim-row `UPDATE`
inside `risk_backfill_service.py` itself (Pitfall-2-safe: an in-memory gate resets on the exact restart this
feature must survive). Call site: add `await _dispatch_risk_exposure_backfill()` in `_scheduler_loop()`
(`scheduler.py:341` area) next to the other two AI-batch dispatcher calls (`:331-332`), same "await these thin
gate-check+create_task calls inline, they never block the tick" comment block.

**Analog 2 (why NOT the enrichment-refresh lock idiom):** `scheduler.py:130-204` (`_dispatch_enrichment_refresh`)
— cite this as the "don't copy this part" contrast: its `asyncio.Lock()` + inline-`await` shape exists because
its atomic delete+insert swap must complete as ONE unit before the gate advances. The backfill is the opposite
case (long-running, chunked, must NOT block the tick) — closer to `_dispatch_ai_batch_prewarm`.

---

### `alembic/versions/044_add_risk_backfill_job.py` (NEW migration)

**Analog 1 (flag-column shape):** `alembic/versions/038_add_exposure_cal_cfg.py` (full file, 33 lines):
```python
revision = "038_add_exposure_cal_cfg"
down_revision = "037_add_exposure_context"

def upgrade() -> None:
    op.add_column("tenants", sa.Column("exposure_criticality_cap", sa.Float(), server_default="0.15", nullable=False))
    op.add_column("tenants", sa.Column("exposure_hard_cap_enabled", sa.Boolean(), server_default="false", nullable=False))
```
Copy: `server_default` (not just Python-side `default`) on every new `tenants` boolean/timestamp column so
existing rows backfill without a data migration; the docstring convention explicitly stating the revision-id
character count (`"038_add_exposure_cal_cfg" is 24 chars — safe`) — **Phase 34 must do the same arithmetic**:
`"044_add_risk_backfill_job"` = 26 chars, safe under the 32-char `alembic_version.version_num` limit.

**Analog 2 (nullable additive columns, no server_default):** `alembic/versions/042_add_risk_exposure_score.py`
— for the new `risk_exposure_backfill_jobs` table's nullable fields (`cursor_vuln_id`, `error_message`,
`completed_at`) that have no meaningful default. `down_revision = "043_index_risk_exposure_score"` (current head,
confirmed live via `.venv/bin/alembic heads` per RESEARCH.md Environment Availability).

**What differs:** this migration creates a whole new TABLE (`op.create_table(...)`, not just `op.add_column`)
— no exact existing precedent for a brand-new table migration was cited in RESEARCH.md; use `039_add_asset_groups.py`
or `041_add_inet_facing_signal.py` (both add new tables per the ROADMAP naming, confirm exact `op.create_table`
shape against one of those files during planning) alongside the flag-column pattern above for the `Tenant`
column additions bundled in the same migration.

---

### `app/tenants/models.py` — 3 new columns (`cutover_risk_exposure_scoring`, `risk_cutover_threshold_ack_at`, `risk_cutover_threshold_ack_diff_hash`)

**Analog:** `app/tenants/models.py:46-52` (exact same file, existing block):
```python
# Phase 32 (EXPO-06) — per-tenant calibration config for
# check_criticality_calibration (app/assets/exposure.py). cap = the
# AUTO-CRITICAL proportion above which the report flags `over_cap`.
# hard_cap_enabled is a documented, deliberately unwired flag — default
# OFF (flag+report only per 32-CONTEXT.md).
exposure_criticality_cap: Mapped[float] = mapped_column(Float, default=0.15, server_default="0.15")
exposure_hard_cap_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```
Copy the exact `Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")` schema shape AND
the comment-block convention (cite the phase, cite the requirement ID, state the default explicitly). Add a
comment explicitly stating **the one meaningful difference from `exposure_hard_cap_enabled`**: this flag is a
REAL behavioral branch in every consumer (not an inert stub) — see 34-CONTEXT.md's locked decision.

`risk_cutover_threshold_ack_at: Mapped[datetime | None]` — mirror `User.last_login_at`'s nullable-timestamp
shape (`app/tenants/models.py:78`, `Mapped[datetime | None] = mapped_column(DateTime(timezone=True))`).

---

### `app/vulnerabilities/service.py:92-99` (`sort="triage"`) — flag branch

**Analog:** itself — the existing `filters.sort ==` chain (`service.py:92-143`) already has 5 branches
(`triage`, `cve_id`, `cvss_v3_score`, `sla_due_at`, `severity`) plus a final `else`; adding a flag-gated variant
of the FIRST branch is structurally identical to how the file already differentiates sort behavior:
```python
# Source: service.py:92-99 (current, byte-identical OFF path)
if filters.sort == "triage":
    data_q = data_q.order_by(
        desc(Vulnerability.cisa_kev),
        nulls_last(desc(Vulnerability.cvss_v3_score)),
        nulls_last(asc(Vulnerability.sla_due_at)),
    )
```
**New shape:**
```python
if filters.sort == "triage":
    if cutover_enabled:  # fetched once per call, see Tenant-fetch pattern below
        data_q = data_q.order_by(
            nulls_last(desc(Vulnerability.risk_exposure_score)),  # NEW primary key
            desc(Vulnerability.cisa_kev),
            nulls_last(desc(Vulnerability.cvss_v3_score)),
            nulls_last(asc(Vulnerability.sla_due_at)),
        )
    else:
        data_q = data_q.order_by(  # byte-identical to today
            desc(Vulnerability.cisa_kev),
            nulls_last(desc(Vulnerability.cvss_v3_score)),
            nulls_last(asc(Vulnerability.sla_due_at)),
        )
```
**Tenant-fetch precedent (this function currently receives only `tenant_id: uuid.UUID`, no `Tenant` row):**
`app/vulnerabilities/sla_service.py:43` (`get_sla_days`'s own caller pattern):
```python
tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
```
Copy this exact one-line scalar Tenant fetch — same negligible-cost indexed-PK-lookup precedent
`exposure.py:424-426` also uses (`hard_cap_enabled = tenant.exposure_hard_cap_enabled if tenant is not None else False`).

---

### `app/vulnerabilities/service.py:534-579` (`get_top_findings_for_ai_batch`) — flag branch

**Analog:** itself, same file, same Tenant-fetch precedent as above.
```python
# Source: service.py:563-577 (current, byte-identical OFF path)
result = await db.execute(
    select(Vulnerability.id)
    .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
    .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
    .order_by(
        nulls_last(desc(Asset.risk_score)),
        desc(Vulnerability.cisa_kev),
        nulls_last(desc(Vulnerability.cvss_v3_score)),
        nulls_last(asc(Vulnerability.sla_due_at)),
    )
    .limit(limit)
)
```
**What differs / must be edited regardless of the flag:** the docstring at `:542-550` ("`Vulnerability` has no
`risk_score` field at all") is now STALE since Phase 33 added `risk_exposure_score` — this comment MUST be
updated as part of this edit, not left misleading (RESEARCH.md line 128). ON-path swaps the primary order key
to `nulls_last(desc(Vulnerability.risk_exposure_score))`; confirm during planning whether the `Asset` outerjoin
is still needed on the ON path (it becomes structurally unnecessary for ordering once scoring is per-finding —
RESEARCH.md line 269 flags this as an open simplification, not a hard requirement).

---

### `app/vulnerabilities/risk_cutover_service.py` (NEW) — pre/post threshold diff (RISK-09)

**Analogs (read-sites to replicate, NOT modify):**
```python
# Source: app/ticketing/rule_engine.py:65-67
min_risk = conditions.get("min_risk_score")
if min_risk is not None and min_risk > 0:
    query = query.where(Asset.risk_score >= min_risk)
```
```python
# Source: app/vulnerabilities/saved_filters.py:104-105 (map_filter_to_conditions)
if filters.get("min_risk_score"):
    conditions["min_risk_score"] = filters["min_risk_score"]
```
Read every `TicketRule.conditions.get("min_risk_score")` and every `SavedFilter.filters.get("min_risk_score")`
exactly as these two sites already do — **do not add a new storage location**, this is a read-only reporting
service. Compute `count(*) WHERE Asset.risk_score >= threshold` (OLD, reuse `rule_engine.py:66-67`'s exact
query shape) vs. `count(*) WHERE Asset.risk_exposure_score >= threshold` (NEW, same shape, different column).

**Ack persistence + audit:** mirror `app/assets/router.py:650` (`asset.bulk_{action}` audit-then-commit):
```python
# Source: assets/router.py:650-651
await audit(db, user, f"asset.bulk_{action}", "asset", None, {"count": len(assets), "reason": reason})
await db.commit()
```
Copy the `audit(...)` (`app/audit.py:136-`, fail-closed per AUDIT-01) **before** `db.commit()` idiom exactly —
add new audit actions `risk_cutover.threshold_ack` / `risk_cutover.flag_enable` to the `## Actions` comment
block at the top of `app/audit.py:53-68` (the codebase convention is to document every action string there).

---

### New admin endpoints — flag-flip + threshold-diff report

**Analog:** `app/assets/router.py:655-665` (`POST /assets/recompute-risk-scores`):
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
Copy: `require_role("admin")` dependency (`app/auth/dependencies.py:124-136`, `ROLE_HIERARCHY`), local import
of the service function inside the handler body (codebase-wide convention, not just this file), thin
handler-calls-service-then-commits shape.

**What differs:** unlike `recompute_risk_scores` (small enough to run inline in the request), the flag-flip
endpoint must NOT run the chunked work inline — it only flips a boolean after checking 2 gates
(`RiskExposureBackfillJob.status == "completed"` AND `risk_cutover_threshold_ack_at` fresh) — mirrors how
`AiBatchJob` *submission* is a separate, fast action from `poll_pending_batches` *retrieval* (RESEARCH.md
line 159). Both new endpoints call `audit(...)` before `db.commit()` per the pattern above; reject with
409/400 (not 200) when a gate fails — no existing endpoint in this codebase currently returns 409 for a
gate-check, confirm the exact status code convention against `app/auth/dependencies.py`'s `HTTPException`
usage during planning (a genuinely new response-shape decision, flagged, not a precedent gap).

---

### `app/vulnerabilities/trends.py:306-318` (`capture_daily_snapshot`) — dual-write new metric keys

**Analog:** itself — the existing `avg_risk` computation block, `trends.py:278-285`:
```python
# Source: trends.py:278-285 (existing, untouched)
avg_risk = (await db.execute(
    select(func.avg(Asset.risk_score)).where(
        Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False), Asset.risk_score.isnot(None)
    )
)).scalar_one()
...
metrics = {
    ...
    "avg_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
    ...
}
```
Copy this exact `func.avg(...)` scalar pattern verbatim, swapping `Asset.risk_score` → `Asset.risk_exposure_score`,
to compute `avg_risk_exposure_score` (a parallel key, added to the SAME `metrics` dict at `trends.py:306-318`,
**unconditional on the cutover flag** per 34-CONTEXT.md's locked decision). Add `asset_risk_scores` (the OLD
key, populated for the FIRST time ever — this is the dead-code fix) and `asset_risk_exposure_scores` (the NEW
parallel key) as `{str(asset.id): score}` dicts, both built from one extra bulk `select(Asset.id, Asset.risk_score,
Asset.risk_exposure_score).where(Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False))` query — mirror the
existing `total_assets` query's `Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False)` filter shape
(`trends.py:288-290`) exactly, for consistency with every other per-tenant Asset query in this function.

**What differs:** this is a pure additive extension of an existing dict literal — no new function, no new file.
`get_risk_score_trend` (`trends.py:165-186`) stays byte-identical (reads `avg_risk_score` only) unless the
planner decides the wire contract's field name should change (RESEARCH.md line 271, open decision).

---

### `app/notifications/alerts.py:189-255` (`_check_risk_score_changes`) — dead-code fix + version-boundary guard

**Analog:** its sibling in the SAME file, `alerts.py:100-141` (`_check_sla_breaches`) — the per-tenant
check-and-notify shape every `_check_*` function in this file already follows:
```python
# Source: alerts.py:120-141 (sibling shape to mirror for the fixed spike check)
for vuln, asset in vulns:
    resource_id = vuln.cve_id or str(vuln.id)
    if await _notification_exists(db, tenant.id, "sla_breach", "vulnerability", resource_id, hours=24):
        continue
    ...
    await create_notification(db, tenant_id=tenant.id, title=..., message=..., severity="high",
                               category="sla_breach", resource_type="vulnerability", resource_id=resource_id,
                               details={...})
    alerts_created += 1
```
The bug being fixed is narrow and localized (`alerts.py:208`, `asset_scores_yesterday = snapshot.metrics.get("asset_risk_scores", {})`
reads a key `capture_daily_snapshot` never wrote) — the fix is entirely on the `trends.py` write side (above),
this file's read side is otherwise already correct and needs only the version-boundary branch added:
```python
# Source: alerts.py:226-234 (existing diff logic, to be duplicated per-version)
for asset in assets:
    old_score = asset_scores_yesterday.get(str(asset.id))
    if old_score is None:
        continue
    new_score = asset.risk_score or 0
    delta = new_score - old_score
    if delta >= 20:
        ...
```
**What differs:** read `tenant.cutover_risk_exposure_scoring` once, then diff `asset_risk_exposure_scores`
(new) vs. `asset_risk_exposure_scores` (new, yesterday) when ON, or `asset_risk_scores` (old) vs.
`asset_risk_scores` (old, yesterday) when OFF — **never cross-version** (RESEARCH.md lines 308-312). The
`_notification_exists(...)` dedup-window call and `create_notification(...)` call stay byte-identical either way.

---

### `backend/tests/test_risk_exposure_backfill.py` (NEW)

**Analogs (3):**
1. **Dispatcher + monkeypatch structure** — `tests/test_scheduler_ai_batch.py:32-51` (`test_batch_blocks_are_non_blocking`)
   and `:130-150` (`test_dispatch_exception_is_caught`) — the `from app.connectors import scheduler as
   scheduler_module` direct-await convention, and the "monkeypatch a slow/failing fake, assert the dispatcher
   itself never raises/blocks" idiom.
2. **24h/gate-state test shape** — `tests/test_scheduler_enrichment_refresh.py:32-52`
   (`test_dispatch_enrichment_refresh_24h_gated`) — for testing the claim-row heartbeat gate analogously
   (cold gate → dispatches; immediate re-call → does not double-claim).
3. **Fixture-seeding pattern** — `tests/test_risk_exposure_service.py:149-204`
   (`test_compute_finding_risk_scores_persists`) — `_seed_asset`/`_seed_vuln` helper functions already exist
   in this file; reuse or mirror them for seeding the fixture set the chunked backfill processes.

**Kill-mid-chunk test (genuinely new — no existing precedent for injecting a mid-transaction failure)**: the
closest structural idiom is `test_scheduler_ai_batch.py:130-150`'s "monkeypatch a function to raise, assert
graceful handling" pattern, but adapted to raise INSIDE the chunk-processing function between the score-UPDATE
step and the cursor-advance step (Pitfall 6, RESEARCH.md lines 357-360) — flagged as new test surface, not a
literal copy.

---

### `backend/tests/test_risk_cutover_ack.py` (NEW)

**Analogs (2):**
1. **Admin-RBAC + audit-row test pattern** — `tests/test_asset_exposure.py:354-367` (`test_override_requires_admin_role`)
   and `:393-425` (`test_asset_override_writes_audit_row`):
```python
# Source: tests/test_asset_exposure.py:354-367
async def test_override_requires_admin_role(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """Non-admin roles (analyst, viewer) are rejected with 403."""
    ...
    for user in (analyst_user, viewer_user):
        c = client_factory(user)
        r = await c.patch(...)
        assert r.status_code == 403, r.text
```
Copy this exact `client_factory(user)` + loop-over-non-admin-roles + `assert r.status_code == 403` idiom for
the flag-flip and ack endpoints, and the audit-row-assertion idiom (`test_asset_exposure.py:394-425`) for
confirming `audit()` fired.
2. **`min_risk_score` fixture pattern** — `tests/test_rule_engine.py:98-103` (`test_min_risk_score_filter`) for
   seeding assets/thresholds the diff computation reads.

---

### `backend/tests/test_severity_trends.py` (EXTEND) + `backend/tests/test_risk_score_change_alerts.py` (NEW)

**Analog for the extension:** itself — `test_severity_trends.py:50-83` (`test_severity_trends_shape_30_day`,
`test_severity_trends_tenant_isolated`) already exercises `capture_daily_snapshot`'s output shape; add
assertions on the two new `metrics` keys following the same `client`/`db_session`/`tenant_a` fixture signature.

**No existing analog for `test_risk_score_change_alerts.py`** — confirmed via grep: no test file in
`backend/tests/` currently references `_check_risk_score_changes` or `_check_sla_breaches` at all; this is a
genuinely new test surface (RESEARCH.md Wave 0 Gaps, line 508). Closest STRUCTURAL analogs to combine: the
snapshot-fixture-construction idiom from `test_severity_trends.py` (build `DailySnapshot` rows directly, not
via the API) + the direct-function-await convention from `test_scheduler_ai_batch.py`
(`from app.notifications import alerts as alerts_module; await alerts_module._check_risk_score_changes(db, tenant)`).

## Shared Patterns

### Tenant-scoping (every query)
**Source:** every query in `risk_exposure_service.py`, `sla_service.py`, `correlation_service.py`
**Apply to:** every new query and the new `UPDATE...FROM` statement in `risk_backfill_service.py`, both new
admin endpoints, `risk_cutover_service.py`
```python
# universal idiom throughout this codebase
.where(Vulnerability.tenant_id == tenant_id, ...)
```
The `UPDATE...FROM (VALUES ...)` chunk-persist statement has NO per-row tenant re-check of its own (unlike
`update().where(id==..., tenant_id==...)` elsewhere) — RESEARCH.md's Security Domain section flags this
explicitly: correctness depends entirely on step 2's `SELECT` being tenant-scoped before the IDs ever reach
the `UPDATE...FROM`. Verify this explicitly in review.

### Admin RBAC + fail-closed audit
**Source:** `app/auth/dependencies.py:124-136` (`require_role`, `ROLE_HIERARCHY`) + `app/audit.py:136-`
(`audit()`, fail-closed per AUDIT-01)
**Apply to:** flag-flip endpoint, threshold-diff/ack endpoint
```python
user=Depends(require_role("admin")),
...
await audit(db, user, "risk_cutover.flag_enable", "tenant", str(user.tenant_id), {...})
await db.commit()
```

### Durable job state, never in-memory
**Source:** `app/ai/models.py:52-90` (`AiBatchJob`) + `app/ai/batch.py:329-368` (`poll_pending_batches`)
**Apply to:** `RiskExposureBackfillJob` + its dispatcher — `_running_syncs`/`_last_ai_batch_prewarm`-style
module globals are explicitly the WRONG shape for anything that must survive a process restart.

### Scheduler-tick dispatch: create_task for long-running, inline-await only for atomic swaps
**Source:** `scheduler.py:73-107` vs `scheduler.py:130-204`
**Apply to:** `_dispatch_risk_exposure_backfill` (must use `create_task`, per the "long-running, partial
progress is fine" bucket — the enrichment-refresh's inline-await is the wrong idiom to copy here).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `backend/tests/test_risk_score_change_alerts.py` | test | event-driven | No existing test anywhere exercises `_check_risk_score_changes` or `_check_sla_breaches` directly (confirmed via grep — zero matches in `tests/`); this notification-check subsystem has never had direct test coverage. Build from the snapshot-fixture idiom in `test_severity_trends.py` + the direct-await convention in `test_scheduler_ai_batch.py`, per the Pattern Assignments section above. |
| Claim-a-chunk concurrency guard (`UPDATE ... RETURNING` heartbeat claim) inside `risk_backfill_service.py` | service (concurrency primitive) | batch | No existing statement in this codebase uses this exact `UPDATE...WHERE stale-or-null...RETURNING` claim-row idiom — every existing concurrency guard is either an in-memory `asyncio.Lock()` (wrong shape, doesn't survive restart) or a WHERE-guard on a *value* column (`sla_due_at.is_(None)`), not a *claim* on a status+heartbeat pair. Genuinely new SQL composed from standard primitives, not a library gap. |
| 409/400 gate-rejection response shape on the flag-flip endpoint | route | request-response | No existing endpoint in this codebase returns 409 for a business-rule gate failure (existing admin endpoints either succeed or 403/404 on RBAC/not-found); confirm the exact `HTTPException` status code convention during planning — flagged as a genuinely new response shape, not a missing precedent search. |

## Anti-Patterns (do NOT do these)

- **NO blocking Alembic data migration.** The historical backfill must never run inside `alembic upgrade` —
  migration `044_add_risk_backfill_job.py` only creates the table/columns (mirrors 038/042's purely-additive,
  nullable-or-server-defaulted shape); all row-level recompute happens via the scheduler-tick dispatcher, never
  inside `op.execute(...)` in a migration file.
- **Do NOT flip `cutover_risk_exposure_scoring` to `True` in this environment.** Build + fixture-test the flag-flip
  endpoint, but per 34-CONTEXT.md's locked decision this environment has no live/at-scale tenant data — the
  actual live flip is accepted debt for a human on a validated stack, exactly like Phases 31/32/33's on-trust waivers.
- **SLA must stay severity-keyed.** Do NOT touch `sla_service.py`'s due-date math (`sla_due_at` computation,
  `sla_service.py:41-115`) or add any `risk_exposure_score`/`Asset.risk_score` read to due-date calculation. Per
  Assumption A1 (resolved), the ONLY defensible SLA-adjacent change is an additive priority-ORDER enhancement
  inside `_check_sla_breaches`'s candidate loop when the flag is ON (order candidates by `risk_exposure_score`
  before the dedup loop) — never a change to when a due date is computed or what severity maps to how many days.
- **Do NOT retarget `min_risk_score` in `rule_engine.py:65-67` or `saved_filters.py:104-105` behind the cutover
  flag.** These stay reading `Asset.risk_score` (OLD) unconditionally this phase — RISK-09 produces a diff+ack
  ARTIFACT only (Assumption A5, resolved). "Helpfully" flipping these for consistency with the other 3 cutover
  consumers is explicitly Pitfall 4 in 34-RESEARCH.md — resist it.
- **Do NOT touch `app/assets/service.py` or `app/assets/schemas.py`.** Not named anywhere in this phase's
  requirements or research; the only `assets` module touched is `app/assets/router.py` (2 new admin endpoints,
  additive) and `app/assets/models.py` is untouched (the new columns land on `Tenant`, not `Asset`).
- **Do NOT write a second scoring function for the backfill.** Reuse `score_finding`/`FindingScoreInputs`
  (`risk_exposure_service.py:141-310`) verbatim — a second implementation risks silently diverging from what a
  live sync computes for the same inputs (Don't-Hand-Roll table, RESEARCH.md line 324).
- **Do NOT use OFFSET-based pagination for the backfill's chunk loop.** Keyset pagination
  (`WHERE id > :cursor ORDER BY id LIMIT :n`) only — OFFSET re-scans and can skip/duplicate rows under
  concurrent writes (new findings syncing in during a multi-hour backfill).
- **Do NOT introduce a `feature_flags` table or any config-JSON flag system.** One `Tenant` boolean column,
  mirroring `exposure_hard_cap_enabled` exactly — no global feature-flag infrastructure exists in this codebase
  and this phase does not justify adding one (Don't-Hand-Roll table, RESEARCH.md line 325).
- **Do NOT use a Redis-based distributed lock for cross-tenant backfill scheduling.** Single-backend-process
  Docker Compose deployment (per CLAUDE.md); the per-tenant DB-row claim (`UPDATE...RETURNING`) is the correct,
  already-sufficient mechanism and degrades safely even if the deployment ever adds replicas.
- **Do NOT boundary-guard `_check_risk_score_changes` without first fixing the dead-code bug.** A test that
  passes because the function returns 0 for every input proves nothing (Pitfall 2) — always include a genuine
  same-version large-delta control case that asserts a NON-zero alert count, before asserting zero across the boundary.
- **Do NOT compute the RISK-09 threshold diff for a tenant whose `RiskExposureBackfillJob.status != "completed"`.**
  The diff endpoint must reject/defer with a clear "not ready yet" response — computing it early produces a
  misleadingly precise but wrong diff (Pitfall 3).

## Metadata

**Analog search scope:** `backend/app/{ai,connectors,vulnerabilities,tenants,assets,notifications,ticketing,audit.py,auth}/`, `backend/alembic/versions/`, `backend/tests/`
**Files scanned (read directly this session):** `app/ai/models.py`, `app/ai/batch.py` (excerpt), `app/connectors/scheduler.py` (full), `app/connectors/enrichment_feeds.py` (excerpt), `app/tenants/models.py` (full), `app/vulnerabilities/sla_service.py` (excerpt), `app/vulnerabilities/service.py` (excerpts x2), `app/vulnerabilities/trends.py` (excerpt), `app/vulnerabilities/risk_exposure_service.py` (excerpts x2), `app/vulnerabilities/models.py` (class index), `app/notifications/alerts.py` (excerpt), `app/ticketing/rule_engine.py` (excerpt), `app/vulnerabilities/saved_filters.py` (excerpt), `app/audit.py` (excerpt), `app/assets/router.py` (excerpt), `alembic/versions/038_add_exposure_cal_cfg.py`, `042_add_risk_exposure_score.py`, `043_index_risk_exposure_score.py` (full), `tests/test_scheduler_enrichment_refresh.py` (excerpt), `tests/test_scheduler_ai_batch.py` (index), `tests/test_risk_exposure_service.py` (excerpt), `tests/test_rule_engine.py` (index), `tests/test_asset_exposure.py` (excerpt), `tests/test_severity_trends.py` (index)
**Pattern extraction date:** 2026-08-11
