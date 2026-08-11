# Phase 34: Historical Recompute & Consumer Cutover - Research

**Researched:** 2026-08-11
**Domain:** Backend-only. Resumable/throttled bulk data recompute (asyncio in-process scheduler + Postgres durable job state), feature-flag-gated consumer cutover (4 read paths), pre/post threshold diff + per-tenant acknowledgment workflow, and version-boundary guards on a notification check + a trend chart. No new external dependencies, no ML, no Celery/queue infra (none exists in this codebase).
**Confidence:** MEDIUM-HIGH — all existing-code reconnaissance is HIGH confidence (read directly, file:line cited below, several genuinely surprising findings verified by direct grep). The resumable-backfill mechanism design and the flag mechanism are HIGH confidence (both synthesize two already-shipped, working precedents in this exact codebase — see below). The exact meaning of "SLA breach detection... reads the new score" is flagged LOW/MEDIUM and resolved via an explicit interpretation in the Assumptions Log, because the current SLA subsystem has **zero** risk-score coupling of any kind today.

## Summary

This is the milestone's highest-risk phase for a concrete, code-verified reason beyond the usual "cutover is risky" framing: **two of the four consumers this phase is asked to "cut over" do not currently read any risk score at all, and one of the two alert mechanisms this phase must boundary-guard is dead code today.** Specifically: (1) SLA due-date computation (`backfill_sla_due_dates`/`check_sla_breaches`, `sla_service.py:41-115`) and the SLA-breach notification (`_check_sla_breaches`, `alerts.py:100-141`) are both purely severity-keyed — neither reads `Asset.risk_score` nor any per-finding score today; the requirement's own text ("SLA windows stay severity-keyed") is best read as reassurance that this phase must not accidentally couple SLA math to risk score, meaning the only defensible "cutover" for this consumer is a *priority-ordering* change (which breach shows first / how it's ranked), not a due-date change. (2) `_check_risk_score_changes` (`alerts.py:189-255`), the "day-over-day risk-spike notification" this phase must version-boundary-guard, reads `snapshot.metrics.get("asset_risk_scores", {})` — a key that `capture_daily_snapshot` (`trends.py:218-329`) **never writes**. This function has always returned `0` alerts in production; it is dead code. Phase 34 cannot "boundary-guard" a check that has never fired — it must first decide whether to actually wire this (populate the per-asset dict, which is a pre-existing bug fix bundled into this phase) or explicitly document it as out-of-scope dead code that remains dead code (in which case RISK-10's alert-storm risk for this specific mechanism is moot, and the research recommends still fixing it, because leaving a named "day-over-day risk-spike notification" broken while claiming to have "version-boundary-guarded" it would be exactly the kind of quiet gap this phase exists to prevent).

The two consumers that genuinely do exist and are cleanly cut-over-able are `sort="triage"` (`service.py:92-99`, currently `KEV desc → CVSS desc → SLA-due asc`, entirely CVSS/KEV/SLA-based, zero risk-score input) and `get_top_findings_for_ai_batch` (`service.py:534-579`, currently ordered by the OLD **asset-level** `Asset.risk_score` with a KEV/CVSS/SLA tiebreak). Both are real, both are the correct places to introduce `risk_exposure_score` (the new **per-finding** column) as the primary sort key — and doing so is a genuine improvement for the AI batch selector specifically, since today's asset-level score can't distinguish which of an asset's several findings is most urgent, while `Vulnerability.risk_exposure_score` can.

The trend chart (`get_risk_score_trend`, `trends.py:165-186`) reads a **scalar tenant-wide average** (`DailySnapshot.metrics["avg_risk_score"]`) computed once daily by `capture_daily_snapshot` (`trends.py:278-285`, `func.avg(Asset.risk_score)`). This is the actual trend-cliff risk: if cutover day flips the metric's *source* from the old score's average to the new score's average, the line chart will show a vertical jump on that one day (different scale, different distribution) with zero prior history to contextualize it. The fix this research recommends is architectural, not cosmetic: **start dual-writing a second, parallel `avg_risk_exposure_score` key into every daily snapshot now (Phase 34, regardless of the cutover flag's state)**, so that by the time a human ever flips the flag on a live stack, the new metric already has a real, continuous trend history stretching back to the day this phase shipped — the chart never needs to draw a line across two different scales, because when the flag flips, the frontend reads from a series that was already being populated in parallel. The same reasoning fixes the alert-storm risk for `_check_risk_score_changes`: dual-write a NEW, correctly-wired `asset_risk_exposure_scores: {asset_id: score}` dict into every snapshot's `metrics` from day one of this phase, and diff **only same-version-to-same-version** (never compare an old-model day-1 value against a new-model day-2 value) — because the new series has been accumulating real day-over-day deltas the whole time the flag was off, the day the flag flips there is no synthetic scale-jump to alert on, only genuine day-over-day change.

`min_risk_score` thresholds live in two places that both ultimately compare against the OLD `Asset.risk_score`: `TicketRule.conditions["min_risk_score"]` (automation rules, read at `rule_engine.py:65-67`) and `SavedFilter.filters["min_risk_score"]` (saved filter presets, `saved_filters.py:104-105`, mapped into rule conditions via `map_filter_to_conditions`). Per the roadmap, RISK-08's cutover list does **not** include the rule engine or saved filters — meaning `Asset.risk_score` itself is never touched by this phase's flag, and these thresholds keep meaning exactly what they meant before. RISK-09's pre/post diff + ack requirement is therefore *not* "fix a threshold that's about to silently break" but a **forward-looking safety gate**: it computes what each tenant's stored numeric threshold (tuned against the old score's distribution) *would* mean if it were ever reinterpreted against the new score's distribution, shows the tenant that diff, and requires an explicit acknowledgment — laying the groundwork so that a *future* phase (not this one) can safely retarget `min_risk_score` conditions at the new score without ever silently reinterpreting a tenant's existing "80" to suddenly mean something different.

The codebase already contains two directly-reusable, battle-tested precedents this phase should synthesize rather than invent from scratch: (1) `backfill_sla_due_dates` (`sla_service.py:41-61`) — a cheap, per-tenant, WHERE-guarded bulk `UPDATE` re-run every scheduler tick (`scheduler.py:277-283`), naturally idempotent because its own `WHERE ... IS NULL` clause excludes already-migrated rows, but **not actually chunked** (it updates the tenant's entire eligible set in one `UPDATE` per severity, an important nuance the roadmap's phrasing "reusing the backfill_sla_due_dates... idiom" glosses over — see Pitfall 1); and (2) `AiBatchJob` (`app/ai/models.py:52-90`) + `poll_pending_batches` (`app/ai/batch.py:329-368`) — a **durable Postgres job-state row**, re-queried by status on every scheduler tick regardless of process restarts, which is the actual "resumable across a restart" precedent this codebase has already shipped and proven (its own docstring: *"a batch submitted before a restart... is still found and retrieved on the very next call, exactly as if the process had never restarted"*). Phase 34's one-time historical recompute should be modeled as a new durable job table (mirroring `AiBatchJob`'s shape) **plus** a keyset resume cursor (a field `AiBatchJob` doesn't need but this job does, since it chunks within a single tenant's dataset rather than delegating to an external batch API), driven by a new gated scheduler-tick dispatcher mirroring `_dispatch_enrichment_refresh`'s lock+gate shape (`scheduler.py:130-204`).

The flag mechanism has a direct, exact precedent already shipped: `Tenant.exposure_hard_cap_enabled` (`app/tenants/models.py:52`, migration `038_add_exposure_cal_cfg.py`) — a per-tenant `Boolean`, `default=False, server_default="false"`, added specifically as a "documented, deliberately unwired flag... default OFF" per Phase 32/EXPO-06. The schema shape is identical to what this phase needs. The one meaningful difference: `exposure_hard_cap_enabled` is read (`exposure.py:426`) but never actually branches behavior — it's returned in a response dict and nothing else (a true no-op stub). Phase 34's flag must be a **real** behavioral switch: every one of the 4 (or, per the findings above, effectively 2-3 genuine) consumer call sites must branch on it. Recommend a new `Tenant.cutover_risk_exposure_scoring: bool` column (or a more precise name — see Open Questions), read once per request/tick and threaded into each consumer's query-building branch, exactly the same shape as the existing `filters.sort ==` branch structure already in `service.py:92-143`.

**Primary recommendation:** Build (a) a new `RiskExposureBackfillJob` model (durable, per-tenant, resumable via a keyset cursor) + a chunked `UPDATE ... FROM (VALUES ...)` bulk-update helper that reuses `score_finding`'s pure per-row logic but persists via true batched `UPDATE...FROM` statements (not `compute_finding_risk_scores`'s current per-row `update()` loop, which is fine for a single sync's open-finding set but not proven to scale as a one-time historical sweep); (b) a gated scheduler-tick dispatcher (mirrors `_dispatch_enrichment_refresh`'s lock pattern) that advances each tenant's job by one chunk per tick, never blocking the scheduler loop; (c) a single new `Tenant.cutover_risk_exposure_scoring` boolean flag (mirrors `exposure_hard_cap_enabled`'s schema shape exactly), default `False`, read at exactly 2 genuine call sites (`sort="triage"`, `get_top_findings_for_ai_batch`) plus 2 forward-looking/dual-write sites (trend snapshot, risk-spike notification) that populate NEW parallel fields regardless of flag state so there is real history by the time a human ever flips it; (d) a pre/post diff report (`GET /admin/risk-cutover/threshold-diff` or similar) reading every `TicketRule.conditions["min_risk_score"]` and `SavedFilter.filters["min_risk_score"]`, computing what each numeric threshold's match-rate would be under the OLD score vs. the NEW `risk_exposure_score` distribution, persisted as a new per-tenant acknowledgment column/table that the cutover flag-flip endpoint checks before allowing `cutover_risk_exposure_scoring = True`; (e) dual-write `avg_risk_exposure_score` + `asset_risk_exposure_scores` into `capture_daily_snapshot`'s `metrics` JSONB starting this phase (unconditional on the flag — this is the actual mechanism that prevents both the trend cliff and the alert storm, by ensuring real continuous history exists before the flag can ever flip).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| One-time historical backfill (chunked, resumable, throttled) | API / Backend (`app/vulnerabilities/risk_exposure_service.py`, extended) | Database (`vulnerabilities`, new job-state table) | Pure compute + DB-orchestration split, mirrors `compute_finding_risk_scores`; durable job state mirrors `AiBatchJob` |
| Backfill dispatch/scheduling | API / Backend (`app/connectors/scheduler.py`, new dispatcher) | — | Same in-process asyncio scheduler tick shape as `_dispatch_enrichment_refresh`/`_dispatch_ai_batch_poll` — no new infra |
| Cutover flag storage + read | Database / Storage (`tenants` table, new column) | API / Backend (every consumer branch) | Mirrors `exposure_hard_cap_enabled`'s exact schema precedent |
| Consumer cutover: `sort="triage"` | API / Backend (`app/vulnerabilities/service.py:92-99`) | — | Query-building branch, same shape as existing `filters.sort ==` chain |
| Consumer cutover: `get_top_findings_for_ai_batch` | API / Backend (`app/vulnerabilities/service.py:534-579`) | — | `order_by()` branch on `Vulnerability.risk_exposure_score` vs. `Asset.risk_score` |
| Consumer cutover: SLA breach detection | API / Backend (`app/vulnerabilities/sla_service.py`, `app/notifications/alerts.py`) | — | No existing risk-score coupling; new coupling (if any) is priority-ordering only, not due-date math — see Assumptions Log A1 |
| Consumer cutover: trend chart | API / Backend (`app/vulnerabilities/trends.py`) | Browser / Client (`trend-chart.tsx`, unaffected — same wire shape) | Dual-write now, switch source key later; no frontend change needed if the wire contract's field NAME stays `avg_risk` |
| Version-boundary guard: risk-spike notification | API / Backend (`app/notifications/alerts.py:189-255`, `app/vulnerabilities/trends.py:218-329`) | — | Requires fixing a pre-existing dead-code bug (`asset_risk_scores` never populated) before it can be guarded at all |
| Pre/post threshold diff + ack | API / Backend (new endpoint/service) | Database (new ack column/table) | Reads `TicketRule`/`SavedFilter` JSONB conditions; gates the flag-flip endpoint |
| Threshold diff + ack UI | Browser / Client (new admin screen) | API / Backend (new endpoint) | Out of this research's backend-only depth — flagged for planner/frontend follow-up; not blocking backend design |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-07 | Idempotent, resumable, throttled, per-tenant-isolated historical recompute; bulk `UPDATE...FROM`; never a blocking Alembic migration; provable by kill-mid-run-and-resume + realistic single-VM load test | "Resumable/Throttled Backfill Design" section — new `RiskExposureBackfillJob` durable table + keyset cursor + chunked `UPDATE...FROM` + scheduler-tick dispatcher, synthesizing `backfill_sla_due_dates` + `AiBatchJob`/`poll_pending_batches` precedents |
| RISK-08 | SLA breach detection, `sort="triage"`, trend charts, `get_top_findings_for_ai_batch` all read the new score when the flag is ON; SLA windows stay severity-keyed; centralize the triplicated severity-tier boundaries | "Flag-Gated Cutover Design" section, per-consumer subsections; Assumptions Log A1 resolves the SLA-breach-detection ambiguity (no existing risk-score coupling exists to "cut over") |
| RISK-09 | Pre/post diff report + explicit re-tuning acknowledgment per tenant for `min_risk_score` automation-rule/saved-filter thresholds before cutover | "Pre/Post Threshold Diff + Ack Design" section — reads `TicketRule.conditions`/`SavedFilter.filters` JSONB (`rule_engine.py:65-67`, `saved_filters.py:104-105`), new ack gate on the flag-flip endpoint |
| RISK-10 | `_check_risk_score_changes` + trend chart are version-boundary-guarded — no alert storm, no trend cliff, fixture-provable across the boundary | "Version-Boundary Guard Design" section — fixes the dead-code `asset_risk_scores` bug, dual-writes parallel new-model metrics from day one, same-version-only diffing |
</phase_requirements>

## Existing-Code Reconnaissance

### 1. `backfill_sla_due_dates` — the idiom named in the roadmap, read exactly as it exists

`backend/app/vulnerabilities/sla_service.py:41-61`:
```python
async def backfill_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Set sla_due_at for all open vulns that don't have one yet."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)
    updated = 0
    for severity, days in sla_days.items():
        result = await db.execute(
            update(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == severity,
                Vulnerability.sla_due_at.is_(None),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.first_detected_at.isnot(None),
            )
            .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
        )
        updated += result.rowcount
    return {"backfilled": updated}
```
- **Called from:** `scheduler.py:277-283` — every 60-second tick, for every active tenant, inline-awaited (not `create_task`), immediately followed by `check_sla_breaches`, then `await db.commit()`.
- **What makes it "idempotent":** the `sla_due_at.is_(None)` WHERE clause. Re-running it costs one full-table-scan-shaped query per severity per tenant per tick, but touches zero rows once every open vuln has a due date — cheap steady-state, not chunked.
- **What it is NOT:** chunked, cursor-resumable, or throttled in any way beyond "the whole eligible set, every tick." For a few hundred/thousand open vulns per tenant this is fine; it is not a template for "safely recompute millions of historical rows across potentially many tenants without blocking the event loop." **This is Pitfall 1 below** — the roadmap's "reusing the backfill_sla_due_dates... idiom" should be read as "reuse the WHERE-guarded-idempotent-tick-driven SHAPE," not "reuse this function's un-chunked bulk-UPDATE-the-whole-set approach verbatim."

### 2. The scheduler-tick dispatch pattern — 3 flavors already shipped, one is the right precedent

`backend/app/connectors/scheduler.py` — the `_scheduler_loop()` (`:206-345`) runs every 60s, `_loop_count` increments each tick, several independently-gated blocks fire per tick:

| Dispatcher | Gate | Dispatch shape | Why |
|---|---|---|---|
| SLA backfill+breach (`:271-285`) | none (runs every tick) | inline `await`, in the SAME `async with async_session_factory()` block, then commits | Cheap enough to run every tick unconditionally |
| `_dispatch_ai_batch_prewarm` (`:73-107`) | in-memory `_last_ai_batch_prewarm`, 24h | `asyncio.create_task` (detached) | Long-running (up to 24h) — must never block the tick |
| `_dispatch_ai_batch_poll` (`:109-127`) | none (every tick) | `asyncio.create_task` (detached) | A batch can finish anytime within its window |
| `_dispatch_enrichment_refresh` (`:130-204`) | in-memory `_last_enrichment_refresh` 24h gate **+ `asyncio.Lock()`** | **inline `await`** (NOT detached) | Atomic delete+chunked-insert swap must complete as ONE unit before the gate advances; a crashed detached task would leave the gate silently advanced with stale data |

**Design implication for Phase 34:** the historical backfill is a mixed case — like `_dispatch_ai_batch_prewarm`, it can run long (hours, for a large tenant) and must NEVER be inline-awaited on the scheduler tick (would stall SLA checks, alert checks, every other tenant's sync-trigger check for the duration). Like `_dispatch_enrichment_refresh`, each unit of work (one chunk) needs a lock/gate so overlapping ticks don't double-process the same chunk if a previous chunk's `asyncio.create_task` hasn't finished before the next 60s tick fires. Recommended shape: dispatch **one chunk per active in-progress job per tick**, via `asyncio.create_task`, guarded by a **per-job in-flight flag stored in the durable job row itself** (not an in-memory dict — an in-memory "is this job currently being chunked" flag would be lost/reset on the exact restart this feature must survive). Concretely: `UPDATE risk_exposure_backfill_jobs SET status='in_progress', last_heartbeat_at=now() WHERE id=:id AND status IN ('pending','in_progress') AND (last_heartbeat_at IS NULL OR last_heartbeat_at < now() - interval '5 minutes') RETURNING id` as the claim-a-chunk guard (a stale-heartbeat reclaim, so a crashed process's job doesn't wedge forever) — this single-statement claim is itself the concurrency-safety mechanism, no new `asyncio.Lock()` needed across tenants since each tenant's job row is claimed independently.

### 3. `AiBatchJob` + `poll_pending_batches` — the actual "survives a restart" precedent

`backend/app/ai/models.py:52-90` (`AiBatchJob`) + `backend/app/ai/batch.py:329-368` (`poll_pending_batches`, full docstring quoted in Summary above). This is the closest existing precedent for "resumable across a process restart" in this codebase — closer than `backfill_sla_due_dates`, which is idempotent-by-WHERE-clause but has no notion of "job," "progress," or "resume point" at all. Key transferable ideas:
- **Durable state, not in-memory.** `_running_syncs`/`_last_*` module globals (used by the connector-sync and 24h-gate dispatchers) are explicitly the WRONG shape here — they reset on restart. `AiBatchJob` rows are queried fresh every tick by `status`.
- **Re-select by ID, not by held ORM reference**, inside each per-job try/except, because `db.rollback()` (needed to recover from one job's failure) expires the whole session's identity map (`batch.py:357-367`docstring) — this exact hazard applies identically to a per-tenant backfill loop that must recover from one tenant's failure without poisoning the next tenant's row.
- **Per-tenant/per-job isolation via try/except inside the loop**, never a single try/except wrapping the whole multi-tenant loop (mirrors `run_batch_prewarm`'s per-tenant isolation, `batch.py:183-188`).

### 4. `repropagate_enrichment` — the actual `UPDATE ... FROM` idiom named in the roadmap

`backend/app/connectors/enrichment_feeds.py:234-262`:
```python
epss_result = await db.execute(
    text(
        "UPDATE vulnerabilities v SET epss_score = e.epss_score, "
        "epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id"
    )
)
```
This is the ONLY existing `UPDATE ... FROM` in the codebase (confirmed via grep for `"FROM"` inside `text(...)` calls in `app/`). It is **unscoped by tenant** (CVE-level facts are global) and **not chunked** (one statement touches the whole table). Phase 34's backfill needs the opposite on both axes — per-tenant-scoped and chunked — but the SQL *shape* (`UPDATE ... FROM (subquery/VALUES) WHERE join-condition`) is exactly right to reuse for the "commit one chunk's worth of already-Python-computed scores in a single statement" step, rather than `compute_finding_risk_scores`'s current N individual `update().where(id==...)` statements per row (fine for a same-transaction full-tenant sync recompute of the open set; not the "bulk `UPDATE ... FROM`" shape the roadmap explicitly asks for at historical-backfill scale).

### 5. `compute_finding_risk_scores` (Phase 33) — the row-scoring logic to reuse, NOT the persistence loop

`backend/app/vulnerabilities/risk_exposure_service.py:313-426` (full function read). Reusable as-is: `score_finding(FindingScoreInputs) -> RiskBreakdown` (pure, `:141-310`), the bulk correlation pre-fetch into a `(cve_id, asset_id) -> sources_count` dict (`:336-345`, avoids N+1), and the MAX-rollup subquery shape (`:392-416`). **Not directly reusable for the historical backfill:** the function currently (a) scopes to `status.in_(["OPEN", "IN_PROGRESS"])` only — REMEDIATED/SUPPRESSED/FALSE_POSITIVE findings are never scored, meaning the historical backfill inherits the same scope decision (a remediated finding never needed a shadow score and doesn't need a historical one either — confirm with planner/discuss-phase, flagged in Open Questions), and (b) persists via a Python-loop of individual `update()` calls, not batched — fine for "however many findings synced today," not proven at "every open finding across a tenant's entire history in one deploy."

### 6. `sort="triage"` — `backend/app/vulnerabilities/service.py:92-99`
```python
if filters.sort == "triage":
    data_q = data_q.order_by(
        desc(Vulnerability.cisa_kev),
        nulls_last(desc(Vulnerability.cvss_v3_score)),
        nulls_last(asc(Vulnerability.sla_due_at)),
    )
```
Zero risk-score input today. Cutover design: `if tenant.cutover_risk_exposure_scoring: order_by(nulls_last(desc(Vulnerability.risk_exposure_score)), desc(Vulnerability.cisa_kev), nulls_last(desc(Vulnerability.cvss_v3_score)), nulls_last(asc(Vulnerability.sla_due_at))) else: <existing branch, byte-identical>` — `risk_exposure_score` becomes the PRIMARY key, the existing 3 become tiebreakers (a finding's `risk_exposure_score` already folds in CVSS/KEV, so leading with it and keeping the others as tiebreakers is a superset, not a replacement, of today's ordering intent). Requires `user.tenant_id` → `Tenant.cutover_risk_exposure_scoring` lookup; `list_vulnerabilities` does not currently load a `Tenant` row at all (only `tenant_id` is threaded through as a UUID) — this is a genuinely new per-request read, one extra indexed PK lookup, negligible cost, same pattern as `get_sla_days`'s existing `Tenant` fetch in `sla_service.py:43`.

### 7. `get_top_findings_for_ai_batch` — `backend/app/vulnerabilities/service.py:534-579`
Full function read (quoted in Summary). Currently orders by `Asset.risk_score` (asset-level, old model) with a KEV/CVSS/SLA-due tiebreak, explicitly documented (`:542-550`) as "the existing deterministic ASSET-02 score... `Vulnerability` has no `risk_score` field at all" — that comment is now STALE as of Phase 33 (`Vulnerability.risk_exposure_score` exists) and MUST be updated as part of this phase's edit, not left as a misleading docstring. Cutover: swap the primary `order_by` key from `nulls_last(desc(Asset.risk_score))` to `nulls_last(desc(Vulnerability.risk_exposure_score))` when the flag is on — this is a strict **improvement** in addition to a cutover, since per-finding ranking is what this selector conceptually wants (picking individual findings for AI narrative pre-warm) and the old asset-level score structurally cannot distinguish which of an asset's findings is most urgent.

### 8. SLA breach detection — confirmed NO existing risk-score coupling
- `sla_service.py:41-115` (`backfill_sla_due_dates`, `recalculate_sla_due_dates`, `check_sla_breaches`, `get_sla_metrics`) — every function keys exclusively on `severity` → `sla_days` lookup and `sla_due_at`/`sla_breached` columns. Zero references to `risk_score` or `risk_exposure_score` anywhere in this file (confirmed via direct read + grep).
- `alerts.py:100-141` (`_check_sla_breaches`) — same, purely `sla_due_at` window + status, zero risk-score input.
- **Conclusion:** there is no existing "SLA breach detection reads a risk score" behavior to flip a flag on. See Assumptions Log A1 for the recommended resolution (a priority-ordering enhancement, not a due-date change) and Open Questions Q1 for what should be confirmed with the user before planning locks this down.

### 9. `_check_risk_score_changes` — dead code today (verified, not assumed)
`backend/app/notifications/alerts.py:189-255`:
```python
asset_scores_yesterday = snapshot.metrics.get("asset_risk_scores", {})
if not asset_scores_yesterday:
    return 0
```
`grep -rn "asset_risk_scores" app/` returns **exactly one match** — this read site. `capture_daily_snapshot` (`trends.py:218-329`) builds a `metrics` dict (`:306-318`) containing `total_vulns`, `open_vulns`, `critical_open`, `high_open`, `remediated`, `sla_breached`, `avg_risk_score` (scalar), `total_assets`, `open_tickets`, `compliance_pct`, `kev_count` — **no `asset_risk_scores` key, ever**. Every `DailySnapshot` row in every tenant's history has `metrics.get("asset_risk_scores", {})` return `{}`, so `_check_risk_score_changes` returns `0` on line 205 (`if not snapshot or not snapshot.metrics: return 0`) or on line 210 (`if not asset_scores_yesterday: return 0`) on literally every call, for every tenant, every day, since this function was written. **This is a genuine pre-existing bug**, not a Phase 34 regression — but Phase 34 is the phase that names this exact function as something to "version-boundary-guard," which is impossible to do meaningfully without first making it actually run.

### 10. Trend chart data source — `backend/app/vulnerabilities/trends.py`
- `capture_daily_snapshot` (`:218-329`) computes `avg_risk = func.avg(Asset.risk_score)` (`:278-285`, OLD score, tenant-wide scalar average across all non-ignored assets with a non-null score) once per tenant per day, stored as `metrics["avg_risk_score"]`.
- `get_risk_score_trend` (`:165-186`) reads the last 90 `DailySnapshot` rows, maps `metrics.get("avg_risk_score", 0)` per day — a flat scalar time series, no per-asset breakdown, no versioning.
- `get_all_trends` (`:189-212`) bundles this into `risk_trend` alongside `vuln_trends`/`mttr_trend`/`severity_trends`, consumed by the frontend `use-trends.ts` → `TrendSection`/`TrendChart` (`frontend/src/components/dashboard/trend-section.tsx`, `frontend/src/components/ui/trend-chart.tsx`) — the wire contract is `{date, avg_risk, open_vulns, critical, sla_breached, compliance_pct}` per day; changing what `avg_risk` MEANS without changing the frontend at all is exactly the trend-cliff mechanism (same field name, silently different scale on either side of one date).
- `capture_all_snapshots` (`:332`+) is the multi-tenant fan-out called daily by the scheduler (`scheduler.py:302-312`, gated on `_last_ticket_sync == now`, i.e. piggybacks on the 24h ticket-sync gate rather than having its own).

### 11. `min_risk_score` — two storage locations, one shared read pattern
- `TicketRule.conditions["min_risk_score"]` (`app/ticketing/models.py:114`, JSONB) — read at `rule_engine.py:65-67`: `if min_risk is not None and min_risk > 0: query = query.where(Asset.risk_score >= min_risk)`. Module docstring (`rule_engine.py:5`) explicitly documents it as "minimum **asset** risk score."
- `SavedFilter.filters["min_risk_score"]` (`app/vulnerabilities/saved_filters.py`, JSONB, `filter_type` discriminates `"vulnerability"` vs `"remediation"`) — stored verbatim from whatever the frontend sends; `map_filter_to_conditions` (`:89-108`) copies it 1:1 (`:104-105`) into a `TicketRule.conditions` dict when a saved filter is linked to an automation rule (`update_saved_filter:64-78`, re-syncs every linked rule's conditions whenever the filter changes). Frontend confirmed to NOT currently expose a live `min_risk_score` query param on any list endpoint (grep of `frontend/src` finds it only in `use-ticket-rules.test.tsx` fixtures) — the live Assets-list equivalent is a **separately named** `min_risk` query param (`assets/router.py:130,161`, mapped from a `risk_band` UI concept in `use-assets.ts:52-65`), which is NOT named in RISK-09's scope (only "automation-rule and saved-filter thresholds") and is NOT touched by this phase's diff/ack design — flagged for the planner as a related-but-out-of-scope surface, same treatment Phase 33 gave `RiskRing.tsx`.
- **Both storage locations compare against `Asset.risk_score` (the OLD score) and RISK-08's cutover list does not include the rule engine.** This is why RISK-09 is a diff+ack, not a live migration — see Summary.

### 12. The existing per-tenant feature-flag precedent — `Tenant.exposure_hard_cap_enabled`
`backend/app/tenants/models.py:46-52` (full comment quoted), `backend/app/assets/exposure.py:402-444` (`check_criticality_calibration`, reads the flag at `:426` but never branches real behavior on it — `:442-444`: *"hard-cap enforcement (off by default) — deliberately NOT wired here... even when hard_cap_enabled is True, this function only reports over_cap; it never downranks"*). Migration: `alembic/versions/038_add_exposure_cal_cfg.py`. **Schema precedent to copy exactly** (`Boolean`, `default=False`, `server_default="false"`); **behavioral precedent to explicitly NOT copy** — Phase 34's flag must be a real branch in each consumer, not a documented-but-inert stub, because "build + fixture-test all machinery" (the user's hard constraint) means the OFF path must be provably safe (byte-identical to today) and the ON path must be provably wired (fixture-tested), unlike `exposure_hard_cap_enabled` where the ON path currently does nothing at all.

### 13. Admin-only recompute endpoint precedent
`assets/router.py:655-665` (`POST /assets/recompute-risk-scores`, `require_role("admin")`) and `:668`+ (`POST /assets/exposure-context/recompute`) — both are synchronous-within-request admin endpoints that call a full-tenant recompute function and return immediately. `require_role` (`app/auth/dependencies.py:124-136`, `ROLE_HIERARCHY = {"owner":4,"admin":3,"analyst":2,"viewer":1}`) is the existing role-gate dependency. Recommend: the flag-flip endpoint (`POST /admin/risk-cutover/enable`, or similar) uses `require_role("admin")` at minimum, gated additionally on the ack having been recorded (RISK-09) — the historical-backfill KICKOFF endpoint (if exposed as a manual trigger rather than purely automatic) should mirror this same admin-gated shape, but the actual chunked work must NOT run inline in the request (unlike `recompute_risk_scores`, which is small enough to run inline) — it must enqueue the durable job row and let the scheduler-tick dispatcher drive it, exactly like `AiBatchJob` submission is separate from `poll_pending_batches` retrieval.

### 14. Audit trail precedent for the ack + flag-flip actions
`app/audit.py:136-` (`audit(db, user, action, resource_type, resource_id, details)`, fail-closed per `AUDIT-01` — docstring `:147-153`: a mutation must not succeed without its audit row landing). The threshold-diff acknowledgment and the flag-flip action are exactly the kind of consequential, rare, admin-only mutation this helper exists for — both should call `audit(...)` before `db.commit()`, mirroring every other admin mutation in the codebase (`asset.bulk_{action}` at `router.py:650` is a representative example).

## Resumable/Throttled Backfill Design (RISK-07)

### New durable job table (mirrors `AiBatchJob`'s shape, adds a resume cursor `AiBatchJob` doesn't need)

```python
class RiskExposureBackfillJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "risk_exposure_backfill_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_risk_backfill_job_tenant"),)  # one job per tenant, ever

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|in_progress|completed|failed
    cursor_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # last-processed Vulnerability.id, keyset resume point
    rows_migrated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_total_estimate: Mapped[int | None] = mapped_column(Integer)  # captured once at job creation, for progress %
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, server_default="500")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
```
Migration: next revision `044_add_risk_backfill_job.py` (30 chars, within the ≤32-char `alembic_version.version_num` constraint), `down_revision = "043_index_risk_exposure_score"`.

**Why one row per tenant (`UniqueConstraint`), not one row per chunk:** mirrors `AiBatchJob`'s one-row-per-submitted-batch shape — the row IS the job's resumable state, updated in place every chunk (`cursor_vuln_id`, `rows_migrated` advance), not appended. This also makes "is tenant X's historical backfill done" a single indexed lookup, which the flag-flip gate (RISK-09/RISK-08) needs: **the cutover flag for a tenant should not be flippable until that tenant's `RiskExposureBackfillJob.status == "completed"`** — enforce this as a check in the flag-flip endpoint, not just a suggestion, closing the "consumer reads a score most of a tenant's own historical findings never received" gap.

### Chunked bulk-update shape (the actual "bulk `UPDATE ... FROM`" the roadmap asks for)

Per chunk (pseudocode, mirrors `repropagate_enrichment`'s `UPDATE...FROM` SQL shape but per-tenant + Python-computed values):
```python
# 1. Claim work + advance heartbeat (single UPDATE, the concurrency guard):
claimed = await db.execute(
    update(RiskExposureBackfillJob)
    .where(
        RiskExposureBackfillJob.tenant_id == tenant_id,
        RiskExposureBackfillJob.status.in_(["pending", "in_progress"]),
        or_(RiskExposureBackfillJob.last_heartbeat_at.is_(None),
            RiskExposureBackfillJob.last_heartbeat_at < now - timedelta(minutes=5)),
    )
    .values(status="in_progress", last_heartbeat_at=now)
    .returning(RiskExposureBackfillJob.cursor_vuln_id, RiskExposureBackfillJob.chunk_size)
)
row = claimed.first()
if row is None:
    return  # already claimed by another in-flight task this tick, or done

# 2. Keyset-paginate the next chunk (NOT OFFSET — stable under concurrent writes):
chunk_q = (
    select(Vulnerability, Asset)
    .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
    .where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        or_(Vulnerability.risk_model_version.is_(None), Vulnerability.risk_model_version != RISK_MODEL_VERSION),
        Vulnerability.id > row.cursor_vuln_id if row.cursor_vuln_id else True,
    )
    .order_by(Vulnerability.id)
    .limit(row.chunk_size)
)
rows = (await db.execute(chunk_q)).all()
if not rows:
    await db.execute(update(RiskExposureBackfillJob).where(...).values(status="completed", completed_at=now))
    return

# 3. Score each row in Python (reuse score_finding — pure, already fixture-tested), then
#    ONE bulk UPDATE...FROM VALUES statement for the whole chunk (not N update() calls):
computed = [(vuln.id, breakdown.final_score, breakdown_json, RISK_MODEL_VERSION) for vuln, asset in rows ...]
await db.execute(text("""
    UPDATE vulnerabilities v SET
        risk_exposure_score = c.score, risk_exposure_breakdown = c.breakdown, risk_model_version = c.version
    FROM (VALUES :values) AS c(id, score, breakdown, version)
    WHERE v.id = c.id::uuid
"""), {"values": computed})  # SQLAlchemy text()+VALUES binding — planner should confirm exact bind-param
                              # shape against the installed SQLAlchemy version; asyncpg driver detail,
                              # not re-verified live this session -- [ASSUMED, low risk, mechanical]

# 4. Advance the cursor + counters (idempotent — safe to re-run this exact chunk if step 3
#    succeeded but this UPDATE crashes before commit, since step 2's WHERE guard would just
#    re-select the same already-scored-but-not-yet-cursor-advanced rows next time, a no-op re-score):
await db.execute(update(RiskExposureBackfillJob).where(...).values(
    cursor_vuln_id=rows[-1][0].id, rows_migrated=RiskExposureBackfillJob.rows_migrated + len(rows),
    last_heartbeat_at=now,
))
await db.commit()  # per-chunk commit — see Throttling below
```

**Idempotency key:** the WHERE-guard `risk_model_version IS DISTINCT FROM 'v1'` (mirrors `backfill_sla_due_dates`'s `sla_due_at.is_(None)` pattern) is the PRIMARY idempotency mechanism — re-running any chunk, or the whole job from scratch, only ever touches rows not yet on the target version. The `cursor_vuln_id` is an **efficiency** optimization (avoid rescanning an already-migrated prefix), not a correctness requirement — this dual-guarantee (WHERE-clause correctness + cursor efficiency) is exactly why the kill-mid-run-and-resume test doesn't need to be delicate about the EXACT moment of the kill: killed before or after any given commit, the next tick's claim query + WHERE-guard naturally picks up from either the cursor or (worst case, cursor update lost) a full but no-op rescan of the already-done prefix.

**Per-tenant isolation:** every query filters `tenant_id` (mirrors every existing query in `compute_finding_risk_scores`, `correlation_service.py`, `risk_score.py`) AND each tenant has its own `RiskExposureBackfillJob` row claimed/advanced independently — one tenant's failure (caught in a per-tenant try/except in the dispatcher loop, mirroring `run_batch_prewarm`'s per-tenant isolation) sets that tenant's job to `status="failed"` with `error_message` populated, without affecting any other tenant's job.

**Throttling:** one chunk (`chunk_size`, default 500) per tenant per scheduler tick (60s), dispatched via `asyncio.create_task` (never inline-awaited — mirrors `_dispatch_ai_batch_prewarm`, not `_dispatch_enrichment_refresh`'s inline-await, because unlike the enrichment swap this is NOT a single atomic all-or-nothing operation — partial progress is the whole point). A tenant with 50,000 open findings resumes over ~100 ticks (~100 minutes) rather than one long blocking operation — this is the "throttled" requirement satisfied structurally, not via an explicit rate-limit/sleep.

## Flag-Gated Cutover Design (RISK-08)

### The flag

```python
# app/tenants/models.py — new column, migration 044 (bundled with the job table migration)
cutover_risk_exposure_scoring: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```
Read once per consumer call (a plain `Tenant` row fetch — `list_vulnerabilities`/`get_top_findings_for_ai_batch` currently only receive `tenant_id: uuid.UUID`, not a `Tenant` object; both need a new `select(Tenant.cutover_risk_exposure_scoring).where(Tenant.id == tenant_id)` scalar fetch, mirroring `get_sla_days`'s existing `Tenant` fetch shape in `sla_service.py:43`).

### Per-consumer branch design

| Consumer | OFF (default) behavior | ON behavior | File:line to edit |
|---|---|---|---|
| `sort="triage"` | Byte-identical to today: `desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at))` | `nulls_last(desc(Vulnerability.risk_exposure_score))` prepended as primary key, same 3 as tiebreakers | `service.py:92-99` |
| `get_top_findings_for_ai_batch` | Byte-identical: `nulls_last(desc(Asset.risk_score))` + tiebreak | `nulls_last(desc(Vulnerability.risk_exposure_score))` replaces the primary key (no outer-join to `Asset` needed anymore for the primary key, though the join stays for... actually the join becomes unnecessary if scoring is per-finding — confirm during planning whether to drop the `Asset` outerjoin entirely on the ON path, a query-simplification opportunity) | `service.py:534-579` |
| SLA breach detection | Byte-identical — no risk-score input today, none added | See Assumptions Log A1 — recommended: within `_check_sla_breaches`'s candidate set, when ON, order candidates by `risk_exposure_score` before the existing per-24h dedup loop, so if a run is ever capped/rate-limited the highest-risk breaches surface first (a genuinely new, small, additive behavior — NOT a due-date change) | `alerts.py:100-141` |
| Trend chart | Byte-identical wire shape (`avg_risk` key name unchanged) | Frontend/consumer reads a NEW key (`avg_risk_exposure_score`) instead, or the SAME `avg_risk` key is fed from the new source — planner/discuss-phase should decide whether the wire contract's field name changes or its SOURCE silently changes once continuity is proven; either way requires the dual-write below to already have real history | `trends.py:165-186`, `:278-329` |

**Severity-tier boundary centralization** (RISK-08's third clause): already fully completed in Phase 33 (`RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM` in `app/assets/risk_score.py:59-61`, imported by `dashboard.py`/`export.py`/`assets/router.py`, verified zero raw literals remain — Phase 33 VERIFICATION.md truth #6). **Nothing left to do here in Phase 34** — the roadmap's RISK-08 wording repeats this from RISK-06 defensively; confirm with the planner that this clause is already satisfied and needs no new task, only a verification-time citation back to Phase 33.

## Pre/Post Threshold Diff + Ack Design (RISK-09)

### Diff computation

For every tenant, for every `TicketRule` with `conditions.get("min_risk_score")` and every `SavedFilter` with `filters.get("min_risk_score")`:
1. **OLD interpretation:** `count(*) WHERE Asset.risk_score >= threshold` (today's actual match set, using the live query shape already in `rule_engine.py:66-67`).
2. **NEW interpretation:** `count(*) WHERE Asset.risk_exposure_score >= threshold` (the SAME numeric threshold, reinterpreted against the new column's distribution) — this requires the tenant's historical backfill (RISK-07) to be complete first, otherwise the NEW count would undercount purely because most assets haven't been scored yet, producing a misleading diff.
3. Report `{threshold, old_match_count, new_match_count, delta, delta_pct}` per rule/filter, surfaced to the tenant admin.

### Acknowledgment gate

New column (mirrors the flag's own schema shape): `Tenant.risk_cutover_threshold_ack_at: Mapped[datetime | None]`. The flag-flip endpoint (`POST /admin/risk-cutover/enable`, `require_role("admin")`, audited per precedent #14 above) must reject with 409/400 if: (a) `RiskExposureBackfillJob.status != "completed"` for this tenant (RISK-07 gate), OR (b) `Tenant.risk_cutover_threshold_ack_at IS NULL` (RISK-09 gate) OR the ack predates the most recent diff-report generation (so a tenant that changes a threshold AFTER acknowledging an old diff must re-acknowledge — store `risk_cutover_threshold_ack_diff_hash` alongside the timestamp, a simple hash of the diff payload, to detect staleness without a full audit-log replay).

**No silent reinterpretation, concretely:** the flag-flip endpoint is the ONLY path that can set `cutover_risk_exposure_scoring = True`, and it structurally cannot succeed without both gates — this is the enforcement mechanism for "must give an explicit re-tuning acknowledgment before its data is cut over," not just a UI convention that could be bypassed by a direct column edit in an admin script (which is, realistically, still possible in this codebase — flagged honestly in Pitfalls, not oversold as unbypassable).

## Version-Boundary Guard Design (RISK-10)

### The trend-cliff fix: dual-write starting this phase, unconditional on the flag

Extend `capture_daily_snapshot`'s `metrics` dict (`trends.py:306-318`) with two NEW keys, populated **every day, regardless of `cutover_risk_exposure_scoring`**:
```python
avg_risk_exposure = (await db.execute(
    select(func.avg(Asset.risk_exposure_score)).where(
        Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False), Asset.risk_exposure_score.isnot(None)
    )
)).scalar_one()
asset_risk_exposure_scores = {str(a.id): a.risk_exposure_score for a in <assets with risk_exposure_score.isnot(None)>}
metrics["avg_risk_exposure_score"] = round(float(avg_risk_exposure), 1) if avg_risk_exposure else 0
metrics["asset_risk_exposure_scores"] = asset_risk_exposure_scores
metrics["risk_model_version_snapshot"] = RISK_MODEL_VERSION  # so a future model bump can also be boundary-guarded
```
**Why this eliminates the cliff structurally, not just cosmetically:** by the time any human ever flips `cutover_risk_exposure_scoring` on a live stack, `DailySnapshot` rows going back to the day this phase deployed already contain real `avg_risk_exposure_score` values — the trend chart's new series has genuine multi-week/month history the FIRST time it's ever displayed, because it was being captured in shadow the whole time the flag was off. There is no "day 1 of the new metric" moment at cutover time; that moment already happened, quietly, when this phase shipped.

### The alert-storm fix: same fix, applied to `_check_risk_score_changes`

1. **Fix the dead-code bug** — populate `asset_risk_scores` (the OLD-model key `_check_risk_score_changes` already reads at `alerts.py:208`) for the first time ever, from `Asset.risk_score` (old score, unconditional). This makes the EXISTING alert start actually firing for the OLD score — a behavior change independent of the new model, worth flagging explicitly to the user/planner since "fix a dormant bug" and "add version-boundary guarding" are two different changes bundled by necessity (you cannot boundary-guard a check between two states if the check has never run in either state).
2. **Add the parallel `asset_risk_exposure_scores` key** (same dict shape, sourced from `Asset.risk_exposure_score`) as described above.
3. **Version-tag the comparison:** `_check_risk_score_changes` reads `tenant.cutover_risk_exposure_scoring` and diffs `asset_risk_exposure_scores` (new) vs. `asset_risk_exposure_scores` (new, yesterday) when ON, or `asset_risk_scores` (old) vs. `asset_risk_scores` (old, yesterday) when OFF — **never new-vs-old or old-vs-new**. Because the new series has been dual-written since this phase shipped, "today's new-model value vs. yesterday's new-model value" is always a same-scale, same-distribution comparison, even on the exact tick the flag flips — there is no synthetic scale-jump to misfire an alert on, because the flag flip does not change WHICH values exist in the snapshot history, only WHICH pre-existing parallel series the comparison function reads.

### Boundary fixture design (for Validation Architecture below)

A fixture spanning the cutover boundary needs: (a) a `DailySnapshot` for "yesterday" with BOTH `asset_risk_scores` (old) and `asset_risk_exposure_scores` (new) populated at their real, pre-cutover values; (b) a `DailySnapshot` for "today" with both keys populated at values reflecting genuine (small) day-over-day drift, NOT a synthetic jump; (c) toggle `tenant.cutover_risk_exposure_scoring` False→True between the two snapshot dates; (d) assert `_check_risk_score_changes` returns 0 spike alerts (no storm) on the boundary day specifically because it's comparing same-version values on both sides; (e) assert `get_risk_score_trend`'s two-day slice shows continuous, non-cliff values for whichever series the flag says to read.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Durable, restart-survivable job state | A new in-memory dict/registry (like `_running_syncs`) | A new table mirroring `AiBatchJob`'s exact shape (durable Postgres row, re-queried by status every tick) | `AiBatchJob`'s own docstring already proves the in-memory shape fails the "survives a restart" requirement this phase explicitly demands |
| Chunked-set pagination | `OFFSET`-based pagination for the backfill loop | Keyset pagination (`WHERE id > :cursor ORDER BY id LIMIT :n`) | OFFSET pagination re-scans and can skip/duplicate rows under concurrent writes (new findings syncing in during a multi-hour backfill); keyset pagination is stable and is the standard pattern for exactly this "resumable chunked sweep of a growing table" scenario |
| Score computation logic | A second, backfill-specific scoring function | `score_finding`/`FindingScoreInputs` (`risk_exposure_service.py:141-310`), already fixture-tested for RISK-01/03/04 in Phase 33 | Two scoring implementations would risk silently diverging; the backfill must produce IDENTICAL scores to what a live sync would have computed for the same inputs |
| Feature-flag storage | A new `feature_flags` table/config-JSON system | A `Tenant` boolean column, mirroring `exposure_hard_cap_enabled` | No global feature-flag system exists in this codebase (confirmed via grep); introducing one for a single flag would be new, unjustified infrastructure |
| Cross-tenant scheduling coordination | A distributed lock (Redis-based mutex across processes) | Per-tenant DB-row claim via `UPDATE ... WHERE status IN (...) AND stale_heartbeat RETURNING` | Single-backend-process deployment (per CLAUDE.md: Docker Compose, no mention of horizontal backend scaling); the existing `asyncio.Lock()` precedent (`_enrichment_refresh_lock`) is IN-PROCESS only and sufficient — a claim-row UPDATE is the correct escalation if multiple processes ever exist, and correctly degrades to a no-op race-safe check even in the single-process case |

**Key insight:** every mechanism this phase needs (durable resumable job state, gated scheduler dispatch, bulk `UPDATE...FROM`, per-tenant boolean feature flag, admin-gated recompute trigger, fail-closed audit) already has a working, shipped precedent somewhere in this codebase. The actual engineering work is synthesis — combining `AiBatchJob`'s durability with `backfill_sla_due_dates`'s idempotent WHERE-guard with `repropagate_enrichment`'s bulk-SQL shape with `exposure_hard_cap_enabled`'s flag schema — not invention of new patterns.

## Common Pitfalls

### Pitfall 1: Reading "reuse backfill_sla_due_dates" too literally
**What goes wrong:** Implementing the historical backfill as one giant per-tenant `UPDATE` (matching `backfill_sla_due_dates`'s actual shape) instead of a chunked, cursor-resumable loop — this would technically be "idempotent" (WHERE-guarded) but NOT throttled, and for a tenant with a very large historical finding set, a single unchunked UPDATE could run long enough to hold a transaction open in a way that blocks other work, defeating "never a blocking Alembic-style migration" in spirit even though it isn't literally an Alembic migration.
**Why it happens:** The roadmap's own phrasing ("reusing the `backfill_sla_due_dates`... idiom") reads as "copy this function," but the function itself isn't chunked — only its idempotency SHAPE (WHERE-guard) is the transferable idea.
**How to avoid:** Chunk explicitly (keyset cursor + `LIMIT`), as designed above. Cite this research's distinction explicitly in the plan so a future reader doesn't "helpfully" simplify back to an unchunked version.

### Pitfall 2: Boundary-guarding a check that has never fired
**What goes wrong:** Writing a "version-boundary-guarded" fixture test for `_check_risk_score_changes` that passes trivially because the function returns 0 for EVERY input (the dead-code bug) — a green test that proves nothing.
**Why it happens:** The dead-code bug is subtle (a `.get(key, {})` default masking a key that's never written) and easy to miss without directly cross-referencing `capture_daily_snapshot`'s actual `metrics` dict keys against every reader.
**How to avoid:** Fix `asset_risk_scores` population FIRST (as a small, explicitly-called-out bug fix within this phase), THEN add the parallel new-model key, THEN write the boundary fixture — verify the fixture actually exercises a spike-detection branch (assert a NON-zero alert count in a same-version-large-genuine-delta control case, to prove the test harness can detect a real spike, before asserting zero across the boundary).

### Pitfall 3: Computing the pre/post threshold diff before the historical backfill completes
**What goes wrong:** Running the RISK-09 diff report against a tenant whose `RiskExposureBackfillJob` is still `in_progress` (or `pending`) would compare "match count under old score" against "match count under new score, where most rows are still NULL" — the NEW count would be artificially low, making every threshold look like it would suddenly match far fewer assets than it should, and a tenant acknowledging that diff would be acknowledging false information.
**Why it happens:** RISK-07 and RISK-09 are naturally built somewhat independently (different sub-teams of work); nothing structurally prevents calling the diff endpoint early unless explicitly gated.
**How to avoid:** The diff-report endpoint itself should check `RiskExposureBackfillJob.status == "completed"` and return a clear "not ready yet" response otherwise, not a misleadingly-precise (but wrong) diff.

### Pitfall 4: Treating `min_risk_score` as if it's in RISK-08's cutover scope
**What goes wrong:** "Helpfully" also flipping `rule_engine.py`'s `Asset.risk_score >= min_risk` to `Asset.risk_exposure_score >= min_risk` behind the SAME flag, reasoning "consistency" — this would silently reinterpret every tenant's stored numeric threshold the exact moment the flag flips, which is precisely what RISK-09 exists to prevent. The roadmap's RISK-08 list is deliberately narrow (SLA/sort/trend/AI-batch); the rule engine and saved filters are RISK-09's territory (diff+ack), not RISK-08's (live cutover).
**Why it happens:** Both features read a "risk score" concept, making them look like natural siblings for a single flag.
**How to avoid:** Keep `Asset.risk_score` reads in `rule_engine.py`/`saved_filters.py`/`assets/router.py`'s `min_risk` param entirely untouched by `cutover_risk_exposure_scoring` in this phase — RISK-09 only produces a diff+ack artifact, it does not itself change what any query reads. Actually retargeting these thresholds is explicitly a FUTURE phase's work (this phase lays the groundwork, per the Summary's "forward-looking safety gate" framing) — confirm this scope boundary with the user in discuss-phase (see Open Questions).

### Pitfall 5: A crashed-and-resumed chunk double-counting `rows_migrated`
**What goes wrong:** If step 3 (the bulk score UPDATE) commits but step 4 (cursor+counter advance) crashes before its own commit, a naive resume would re-select and re-score the same chunk (harmless per the idempotency WHERE-guard) but a naive `rows_migrated += len(rows)` would double-count that chunk's rows in the progress counter, corrupting the "how far along is this tenant" metric shown in any progress UI.
**Why it happens:** Steps 3 and 4 are two separate statements/commits in the design above (deliberately, so step 3's chunk can be large while step 4's counter update is cheap) — an all-or-nothing wrapper around both would be safer but reduces chunk-commit granularity (throttling wants frequent commits).
**How to avoid:** Either (a) wrap steps 3+4 in the SAME transaction (one commit for both — simplest, recommended, since both are already per-chunk-sized and cheap together), or (b) if kept separate, derive `rows_migrated` from a query (`count() WHERE risk_model_version = 'v1'`) rather than an incrementing counter, making it naturally idempotent-to-recompute rather than accumulative. Recommend (a) to the planner — it's strictly simpler and removes this whole failure class.

### Pitfall 6: Kill-mid-run test that doesn't actually test mid-CHUNK, only mid-JOB
**What goes wrong:** A "kill-mid-run-and-resume" test that only kills the dispatcher BETWEEN ticks (i.e., between two whole, cleanly-committed chunks) proves resumability but never exercises the actual crash-mid-chunk scenario that Pitfall 5 and the idempotency WHERE-guard exist to handle.
**Why it happens:** It's much easier to write a test that stops calling an async function than one that injects a failure mid-transaction.
**How to avoid:** Write at least one test that raises an exception INSIDE the chunk-processing function after the score-UPDATE step but before the cursor-advance step (or after the cursor-advance but before commit) — a `monkeypatch` raising on the second of two DB calls is the standard way to simulate this, consistent with `test_scheduler_enrichment_refresh.py`'s own `monkeypatch`-based dispatcher tests.

## Code Examples

### Existing gated+locked scheduler dispatcher to mirror (`scheduler.py:130-204`, abbreviated)
```python
# Source: backend/app/connectors/scheduler.py:177-203
_enrichment_refresh_lock = asyncio.Lock()

async def _dispatch_enrichment_refresh() -> None:
    if _enrichment_refresh_lock.locked():
        return
    global _last_enrichment_refresh
    async with _enrichment_refresh_lock:
        try:
            now = datetime.now(UTC)
            if _last_enrichment_refresh is None or (now - _last_enrichment_refresh).total_seconds() >= 86400:
                # ... do the work, advance the gate ONLY on success ...
                if status_ok:
                    _last_enrichment_refresh = now
        except Exception as e:
            logger.error("enrichment_refresh_dispatch_error", error=str(e))
```
Phase 34's dispatcher should follow this try/except-wraps-everything, log-and-continue shape, but replace the in-memory `_last_*` gate with the durable per-tenant `RiskExposureBackfillJob` claim-row UPDATE (Pitfall-2-safe, restart-survivable).

### Existing durable resume-from-Postgres precedent (`app/ai/batch.py:340-368`, docstring only, full function not reproduced for brevity — read directly for implementation)
```python
# Source: backend/app/ai/batch.py:340-346
"""RESUME-FROM-POSTGRES (RESEARCH #2, T-26-08): selects EVERY `AiBatchJob`
row with `status == "in_progress"` from the DURABLE table -- never an
in-memory registry -- so a batch submitted before a restart... is
still found and retrieved on the very next call, exactly as if the
process had never restarted."""
```

### Existing bulk `UPDATE ... FROM` shape to adapt (`enrichment_feeds.py:251-256`)
```python
# Source: backend/app/connectors/enrichment_feeds.py:251-256
epss_result = await db.execute(
    text(
        "UPDATE vulnerabilities v SET epss_score = e.epss_score, "
        "epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id"
    )
)
```

### Existing per-tenant feature-flag schema + read precedent (`app/tenants/models.py:52`, `app/assets/exposure.py:424-426`)
```python
# Source: backend/app/tenants/models.py:52
exposure_hard_cap_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

# Source: backend/app/assets/exposure.py:424-426
tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
hard_cap_enabled = tenant.exposure_hard_cap_enabled if tenant is not None else False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `Vulnerability.risk_exposure_score` only populated going forward, at sync time (Phase 33) | Historical open findings backfilled via a resumable chunked job | This phase | Every tenant's existing open findings, not just newly-synced ones, get a shadow score |
| `sort="triage"`/`get_top_findings_for_ai_batch` use CVSS/KEV/old-asset-score | Optionally read the new per-finding `risk_exposure_score` behind a per-tenant flag | This phase (flag OFF by default in this environment) | No live behavior change until a human flips the flag on a validated stack |
| `DailySnapshot.metrics` has exactly one risk metric (`avg_risk_score`, old model) + one broken key (`asset_risk_scores`, never populated) | Dual-tracks both old and new model metrics, `asset_risk_scores` finally populated | This phase | Trend/alert continuity exists BEFORE the flag can ever flip, eliminating the cliff/storm risk structurally |
| `min_risk_score` thresholds have no cross-model translation | Pre/post diff computed and requires ack | This phase | Groundwork for a FUTURE phase to safely retarget thresholds; this phase does not itself retarget them |

**Deprecated/outdated:** None — purely additive, mirrors Phase 33's own "shadow-first, never overwrite the live path" discipline.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "SLA breach detection... reads the new score" (RISK-08) has no existing risk-score-coupled code to cut over, so the correct interpretation is a NEW, small, additive priority-ordering enhancement (order breach candidates by `risk_exposure_score` when the flag is ON) — NOT a change to due-date computation, which the requirement's own "SLA windows stay severity-keyed" clause explicitly protects | "Flag-Gated Cutover Design" — SLA breach detection row | If the user actually intends something more substantial (e.g., a NEW SLA-tier system where risk_exposure_score influences due-date length, not just ordering), this phase's scope for that consumer would need to expand significantly — moderate risk, should be confirmed in discuss-phase before planning locks task scope |
| A2 | `_check_risk_score_changes`'s dead-code bug (`asset_risk_scores` never populated) should be FIXED as part of this phase (not left dead, not deferred) — because RISK-10 names this exact function as something to boundary-guard, and guarding a no-op is meaningless | "Version-Boundary Guard Design" | If the user considers fixing a pre-existing unrelated bug out of scope for this phase, RISK-10's "no alert storm" claim for this specific mechanism becomes vacuously true (a broken check can't storm) rather than meaningfully proven — low risk either way since a vacuous pass doesn't create a NEW problem, but it would misrepresent what was actually verified |
| A3 | The historical backfill's status scope matches `compute_finding_risk_scores`'s existing scope — OPEN/IN_PROGRESS findings only; REMEDIATED/SUPPRESSED/FALSE_POSITIVE findings are never backfilled (they were never shadow-scored going forward either, so there's no inconsistency to fix) | "Existing-Code Reconnaissance #5" | If trend/historical-reporting features ever want risk_exposure_score on CLOSED findings (e.g., "what was this finding's risk when it was open"), this scope decision would need revisiting — low risk, consistent with Phase 33's own established scope |
| A4 | One `RiskExposureBackfillJob` row per tenant (not per chunk, not re-created on retry) is the right granularity, with `status="failed"` requiring an explicit admin action (not shown in this research) to reset to `"pending"` and retry | "Resumable/Throttled Backfill Design" | If tenants need self-service retry without admin intervention, an additional endpoint/UI affordance is needed — not designed here, flagged for planner; low risk, additive |
| A5 | `min_risk_score` retargeting to the new score is explicitly OUT of this phase's scope — RISK-09 produces a diff+ack artifact only, no query anywhere changes what it reads as a result of this phase | "Pitfall 4" | If the user intends RISK-09's ack to actually GATE a live retarget within this same phase (not just document tenant awareness for a future phase), the design needs an additional "apply" step after ack — moderate risk, should be confirmed in discuss-phase (see Open Questions Q2) |
| A6 | Single-backend-process deployment (no horizontal scaling) makes an in-process claim-row UPDATE sufficient for cross-tick concurrency safety, without needing a Redis-based distributed lock | "Don't Hand-Roll" | If the production deployment ever runs multiple backend replicas (CLAUDE.md doesn't mention this today, but the user's MEMORY.md references "multi-replica state" work from Phase 1 of v1.0 — worth double-checking), the claim-row UPDATE's `RETURNING` + status-transition IS already safe under true multi-process concurrency (it's a single atomic SQL statement, not a check-then-act race) — so this assumption is actually low-risk even if wrong, since the mechanism generalizes correctly; flagged for completeness, not because a redesign would be needed |

**If this table is empty:** N/A — six assumptions, none block starting the plan; A1/A5 are the two most consequential and should be explicitly resolved in discuss-phase since they change the shape of two of the four named consumers.

## Open Questions

1. **What does "SLA breach detection reads the new score" concretely mean, given no existing coupling exists?**
   - What we know: `sla_service.py` and `alerts.py:_check_sla_breaches` are purely severity/due-date-keyed today; there is no existing risk-score input anywhere in the SLA subsystem.
   - What's unclear: whether the user wants (a) a priority-ORDERING enhancement only (this research's recommendation, Assumption A1), (b) a new dashboard/notification surface that shows risk_exposure_score alongside SLA-breach info without changing any existing function, or (c) something more substantial involving due-date math (which would contradict "SLA windows stay severity-keyed" if taken further).
   - Recommendation: confirm (a) in discuss-phase before planning; it's the smallest, safest interpretation consistent with every explicit constraint in the requirement text.

2. **Does RISK-09's acknowledgment actually gate a live retarget of `min_risk_score` conditions in THIS phase, or only produce an artifact for a future phase?**
   - What we know: RISK-08's explicit cutover list (SLA/sort/trend/AI-batch) does not include the rule engine or saved filters; `Asset.risk_score` is untouched by the flag in this research's design.
   - What's unclear: whether "before its data is cut over" (RISK-09's exact wording) implies the ack should also flip something for THIS tenant's automation rules specifically, distinct from the global `cutover_risk_exposure_scoring` flag.
   - Recommendation: treat RISK-09 as diff+ack-only (Assumption A5) unless the user corrects this during discuss-phase; the smaller scope is strictly safer to ship and does not foreclose a follow-up phase.

3. **Is a single global-with-per-tenant-ack flag column sufficient, or does the user want the flag flip itself to also be per-tenant self-service (not admin-only)?**
   - What we know: the user's hard constraint asks for "the cleanest per-tenant (or global-with-per-tenant-ack) flag mechanism" and explicitly states a human flips it on a validated live stack, not an in-app self-service toggle, in THIS environment.
   - What's unclear: whether the flag-flip endpoint should exist as a real, callable admin API in this phase (built + fixture-tested per the hard constraint) or whether it's acceptable to design the flag/gates without actually exposing a flip endpoint at all (e.g., flipped via direct DB/ops action only).
   - Recommendation: build the endpoint (admin-role-gated, both-gates-enforced) since "build + fixture-test all machinery" implies the flip mechanism itself must be tested, not just the column's existence — but keep it clearly documented as "not to be called against live tenant data in this environment."

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | New job table, chunked UPDATE...FROM | ✓ (docker `getvul-postgres-1`, healthy) | — (not queried this session) | — |
| Redis | Session/cache — not directly used by this phase's new code | ✓ (docker `getvul-redis-1`, healthy) | — | — |
| Python | Backend runtime | ✓ | 3.14.6 (system); backend `.venv` present with sqlalchemy/alembic/pytest importable | — |
| Alembic | New migration `044_*` | ✓ | head confirmed `043_index_risk_exposure_score` | — |
| pytest | Validation | ✓ (per backend_test_env note: needs `ENCRYPTION_KEY`/`JWT_SECRET_KEY` env vars, run per-file) | — | — |

No missing dependencies. This phase introduces no new external service/library dependency — everything is built from primitives already in the stack (SQLAlchemy, asyncio, Postgres `UPDATE...FROM`).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend `pyproject.toml` `[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` |
| Quick run command | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/pytest tests/test_risk_exposure_backfill.py -x` |
| Full suite command | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... .venv/bin/pytest tests/` (run per-file during development per project memory; full-dir only as final gate) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-07 | Chunked backfill processes a fixture set of open findings, persists correct scores identical to `score_finding` | unit/integration | `pytest tests/test_risk_exposure_backfill.py::test_chunk_processes_correct_rows -x` | ❌ Wave 0 |
| RISK-07 | Kill-mid-chunk (exception injected after score-UPDATE, before cursor-advance) then resume produces correct final state, no double-count | integration | `pytest tests/test_risk_exposure_backfill.py::test_kill_mid_chunk_resumes_correctly -x` | ❌ Wave 0 |
| RISK-07 | Job resumes correctly after a SIMULATED PROCESS RESTART (fresh DB session/query, no in-memory state carried over) | integration | `pytest tests/test_risk_exposure_backfill.py::test_resume_survives_simulated_restart -x` | ❌ Wave 0 |
| RISK-07 | Realistic single-VM load fixture: seed N (e.g. 20,000) open findings for one tenant, run the full chunk loop to completion, assert wall-clock/throughput bound and that other scheduler work (e.g. a concurrent SLA check) isn't starved | integration (fixture-level, not live load test — no live/at-scale tenant data exists per user constraint) | `pytest tests/test_risk_exposure_backfill.py::test_large_tenant_backfill_throughput -x` | ❌ Wave 0 |
| RISK-07 | Per-tenant isolation: tenant A's job failure does not affect tenant B's job progress | unit | `pytest tests/test_risk_exposure_backfill.py::test_tenant_failure_isolated -x` | ❌ Wave 0 |
| RISK-08 | `sort="triage"` ON reads `risk_exposure_score` primary; OFF is byte-identical to pre-Phase-34 ordering | unit | `pytest tests/test_vulnerabilities.py::test_triage_sort_cutover_flag -x` (or new file) | ⚠️ confirm during planning |
| RISK-08 | `get_top_findings_for_ai_batch` ON reads per-finding `risk_exposure_score`; OFF is byte-identical | unit | `pytest tests/test_risk_exposure_service.py::test_ai_batch_selector_cutover_flag -x` (extend existing file) | ⚠️ confirm during planning |
| RISK-08 | Flag OFF (default) produces zero behavior change across all 4 consumers — regression/characterization test | regression | `pytest tests/test_vulnerabilities.py tests/test_sla_service.py tests/test_severity_trends.py -x` (existing suites, must stay green unmodified) | ✓ exists (extend assertions) |
| RISK-09 | Pre/post diff computes correct old-vs-new match counts for a fixture set of thresholds | unit | `pytest tests/test_risk_cutover_ack.py::test_threshold_diff_computation -x` | ❌ Wave 0 |
| RISK-09 | Flag-flip endpoint rejects when backfill incomplete OR ack missing/stale; succeeds only when both gates pass | integration | `pytest tests/test_risk_cutover_ack.py::test_flag_flip_requires_both_gates -x` | ❌ Wave 0 |
| RISK-10 | `asset_risk_scores`/`asset_risk_exposure_scores` are both populated in every new `DailySnapshot` | unit | `pytest tests/test_severity_trends.py::test_snapshot_populates_asset_risk_dicts -x` (extend existing file) | ⚠️ confirm during planning |
| RISK-10 | Boundary fixture: snapshots spanning a flag flip produce zero storm alerts and a continuous (non-cliff) trend read | integration (fixture) | `pytest tests/test_risk_score_change_alerts.py::test_cutover_boundary_no_storm_no_cliff -x` | ❌ Wave 0 |
| RISK-10 | Control case: a genuine same-version large delta DOES still alert (proves the boundary fixture isn't just testing a broken/no-op check — Pitfall 2) | unit | `pytest tests/test_risk_score_change_alerts.py::test_genuine_spike_still_alerts -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** run the specific new/modified test file only (per-file, per `backend_test_env` constraint).
- **Per wave merge:** full backend suite (`pytest tests/`).
- **Phase gate:** full suite green + the flag-OFF characterization tests explicitly re-run and confirmed byte-identical to pre-Phase-34 baseline, before `/gsd-verify-work`. Given this phase's stated risk level, recommend the verifier also manually re-read `_check_risk_score_changes` and `capture_daily_snapshot` post-implementation to confirm the dead-code fix (Pitfall 2) was actually addressed, not just fixture-passed.

### Wave 0 Gaps
- [ ] `backend/tests/test_risk_exposure_backfill.py` — new file, covers RISK-07 entirely (chunking, resume, kill-mid-chunk, per-tenant isolation, throughput fixture). No existing test covers chunked/resumable job state anywhere in the codebase (`test_scheduler_ai_batch.py`/`test_scheduler_enrichment_refresh.py` cover GATED DISPATCH, not chunked resumable state — genuinely new test surface).
- [ ] `backend/tests/test_risk_cutover_ack.py` — new file, covers RISK-09's diff computation + flag-flip gate enforcement.
- [ ] New `RiskExposureBackfillJob` model + migration `044_add_risk_backfill_job.py` + `Tenant.cutover_risk_exposure_scoring` + `Tenant.risk_cutover_threshold_ack_at` columns — none exist yet, all net-new.
- [ ] Extend `tests/test_severity_trends.py` (or create `test_daily_snapshot.py` if none exists at the right granularity — confirm during planning) with assertions on the two new snapshot metric keys.
- [ ] New `tests/test_risk_score_change_alerts.py` (confirm no existing file already covers `_check_risk_score_changes` — a grep for `_check_risk_score_changes` in `tests/` should be run at planning time; not found in this session's `ls tests/` sweep, likely genuinely new).
- [ ] Extend `tests/test_risk_exposure_service.py` (existing, Phase 33) with the flag-cutover branch tests for `get_top_findings_for_ai_batch`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | Every new query filters `tenant_id` (mirrors every existing query in this domain); the flag-flip and ack endpoints use `require_role("admin")` at minimum (`app/auth/dependencies.py:124`), matching the existing `recompute-risk-scores`/`exposure-context/recompute` precedent |
| V5 Input Validation | Minor new surface | The flag-flip endpoint takes no dynamic user input beyond the tenant's own admin action (no new query params to sanitize); the threshold-diff endpoint reads existing stored JSONB, no new user-supplied values |
| V6 Cryptography | No | Not applicable |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant leakage in the backfill's bulk chunk queries/UPDATE | Information Disclosure / Tampering | Every query and the `UPDATE...FROM` statement itself must filter/join on `tenant_id` — the `UPDATE ... FROM (VALUES ...)` shape in this design only ever contains IDs already fetched via a `tenant_id`-scoped `SELECT`, so cross-tenant write is structurally impossible as long as step 2's SELECT is correctly scoped (verify this explicitly in review — a bulk UPDATE...FROM has no per-row tenant re-check of its own, unlike the individual `update().where(id==..., tenant_id==...)` pattern elsewhere) |
| Flag-flip bypass via direct DB access | Elevation of Privilege (out of the app's own control boundary) | Acknowledged honestly in this research (Pitfall/A-note) — the app-level gate (endpoint enforcing both checks) is the intended control surface; a superuser DB script bypassing it is an operational-trust boundary, not a code defect, consistent with how every other admin-only mutation in this codebase is protected |
| Audit-trail gap on the ack/flip actions | Repudiation | Use `audit()` (`app/audit.py:136`, fail-closed) for both the ack-recording action and the flag-flip action, mirroring every other consequential admin mutation in the codebase |

## Sources

### Primary (HIGH confidence)
- Direct codebase reads (file:line cited throughout): `backend/app/vulnerabilities/sla_service.py`, `backend/app/connectors/scheduler.py`, `backend/app/connectors/enrichment_feeds.py`, `backend/app/ai/models.py`, `backend/app/ai/batch.py`, `backend/app/vulnerabilities/service.py`, `backend/app/vulnerabilities/dashboard.py`, `backend/app/vulnerabilities/trends.py`, `backend/app/notifications/alerts.py`, `backend/app/ticketing/rule_engine.py`, `backend/app/ticketing/models.py`, `backend/app/vulnerabilities/saved_filters.py`, `backend/app/tenants/models.py`, `backend/app/assets/exposure.py`, `backend/app/assets/router.py`, `backend/app/assets/risk_score.py`, `backend/app/vulnerabilities/risk_exposure_service.py`, `backend/app/vulnerabilities/models.py`, `backend/app/assets/models.py`, `backend/app/audit.py`, `backend/app/auth/dependencies.py`, `backend/alembic/versions/*` (naming/sequencing), `backend/tests/conftest.py`, `backend/tests/test_scheduler_ai_batch.py`, `backend/tests/test_scheduler_enrichment_refresh.py`, `backend/tests/test_rule_engine.py`, `backend/tests/test_severity_trends.py`
- `frontend/src/lib/queries/use-assets.ts`, `use-top-triage.ts`, `use-ticket-rules.test.tsx`, `frontend/src/components/dashboard/trend-section.tsx` — confirmed wire contracts and confirmed the absence of a live `min_risk_score` frontend consumer
- Live environment probes this session: `docker ps` (postgres/redis healthy), `.venv/bin/alembic heads` (confirmed `043_index_risk_exposure_score`), `.venv/bin/python -c "import sqlalchemy, alembic, pytest"` (deps importable)

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` (RISK-07..10 exact text), `.planning/ROADMAP.md` (Phase 34 goal/success-criteria, dependency on Phase 33)
- `.planning/phases/33-risk-exposure-model-definition/33-RESEARCH.md` + `33-VERIFICATION.md` — the Phase 33 input contract (`risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version` columns, shadow-compute contract, zero-consumer gate, severity-tier centralization already complete)

### Tertiary (LOW confidence)
- The exact SQLAlchemy `text()`-with-`VALUES`-list bind-parameter mechanics for the chunked `UPDATE...FROM` (marked `[ASSUMED, low risk, mechanical]` inline above) — not executed live this session; the planner/executor should verify the exact binding syntax against the installed SQLAlchemy version before finalizing the chunk-persist implementation (a mechanical detail, not a design-level risk)

## Metadata

**Confidence breakdown:**
- Existing-code reconnaissance: HIGH — every claim is a direct file:line read or grep this session, including two genuinely surprising negative findings (dead `asset_risk_scores` code, zero SLA-risk-score coupling) verified by grep, not inferred
- Resumable/throttled backfill design: HIGH — synthesizes two already-shipped, working precedents (`AiBatchJob`/`poll_pending_batches`, `backfill_sla_due_dates`) rather than inventing a novel mechanism
- Flag-gated cutover design: HIGH for the 2 genuine consumers (sort/AI-batch), MEDIUM for SLA breach detection (interpretation flagged, Assumption A1) and trend chart (dual-write mechanism is HIGH confidence, exact wire-contract decision for the frontend is a planner/discuss-phase call)
- Threshold diff + ack design: MEDIUM — the computation and gating mechanism are straightforward extensions of existing query shapes (HIGH), but the exact scope boundary (diff+ack-only vs. also-retargeting) is an open question requiring user confirmation (Assumption A5)
- Version-boundary guard design: HIGH — the dual-write mechanism is a direct, low-risk architectural fix; MEDIUM on whether fixing the pre-existing dead-code bug is in-scope for this phase (Assumption A2), though this research recommends treating it as in-scope
- Validation architecture: MEDIUM — test framework/commands HIGH confidence (verified live); exact file organization is a planner recommendation, not an exhaustive audit of every possible existing test file

**Research date:** 2026-08-11
**Valid until:** 30 days (stable backend domain; the highest-risk element — user confirmation of Assumptions A1/A5 — should happen well before that window via discuss-phase, not via research re-run)
