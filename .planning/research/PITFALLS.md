# Pitfalls Research

**Domain:** Replacing an authoritative deterministic risk score, adding scanner-native signal enrichment, auto-inferring asset exposure context, and making scanner provenance a first-class filterable/badged dimension — in an EXISTING production multi-tenant vulnerability-triage platform (GetVul v4.0 "Enriched Risk Exposure & Source-Aware Triage")
**Researched:** 2026-08-04
**Confidence:** HIGH for GetVul-specific findings (all verified by direct code inspection of `backend/app/assets/risk_score.py`, `backend/app/vulnerabilities/correlation_service.py`, `backend/app/connectors/scheduler.py`, all six connector modules, `notifications/alerts.py`, `ticketing/rule_engine.py`, `assets/models.py`, `vulnerabilities/models.py`, `cspm/models.py`) — every pitfall below is grounded in a real, current code path, not a generic domain claim. MEDIUM for general industry framing (score-migration/backfill patterns) which is standard SRE/data-migration practice, not sourced from a single external doc.

## Why This Milestone Is Structurally Dangerous

`Asset.risk_score` is not a UI nicety in this codebase — it is read, sorted on, thresholded against, or diffed in at least **11 separate call sites** across `export.py`, `search.py`, `users/router.py`, `assets/service.py`, `assets/router.py`, `ticketing/service.py`, `ticketing/rule_engine.py`, `ticketing/router.py`, `vulnerabilities/service.py`, `vulnerabilities/dashboard.py`, `vulnerabilities/trends.py`, `notifications/alerts.py`, and `app/ai/prompt_builder.py` / `app/vulnerabilities/service.py`'s AI batch-scope selector — and it is referenced by **tenant-authored data** (saved filters' `min_risk_score`, ticketing automation rules' `min_risk_score` condition) that lives in the database, not in code, and will not get a code review when the formula changes underneath it. Meanwhile the "clean slate" rebuild must run inside a single-VM, in-process-scheduler deployment with no task queue — the existing `compute_risk_scores()` already does a per-asset Python-loop `UPDATE` (not a bulk statement) and is already called synchronously after every connector sync. Every pitfall below traces back to one of these two facts: **the score has more silent dependents than the milestone's own framing names**, and **the only compute substrate available for a one-time recompute is the same single asyncio event loop that also runs sync ticks, SLA checks, and AI batch dispatch.**

## Critical Pitfalls

### Pitfall 1: Tenant-Authored Automation Rules and Saved Filters Silently Reinterpret the New Score

**What goes wrong:**
`backend/app/ticketing/rule_engine.py` conditions include `min_risk_score` (a tenant-configured automation rule condition — "auto-create a Jira ticket when an asset's risk score ≥ 80"), and `backend/app/vulnerabilities/saved_filters.py` persists `min_risk_score` from analyst-saved filter views. Neither is code — both are rows in the tenant's database, authored before the milestone existed, expressing trust in the *old* 0–100 distribution (piecewise power/log curve, KNEE_SCORE=45 at raw=120). The instant the new model computes a differently-shaped distribution, every existing rule and saved filter silently starts firing on a different population of assets — some tenants get a flood of new auto-created tickets, others go quiet — with no error, no warning, and no diff surfaced to the tenant.

**Why it happens:**
The score's numeric meaning ("80" means "critical-tier, multiple exploitable CRITICALs") is implicit in the piecewise curve's shape, not declared anywhere machine-readable. A clean-slate rebuild naturally changes that shape (different inputs, different curve), but nothing forces a review of who else is reading the number as a fixed reference point. This is exactly the class of dependent the milestone's own framing ("SLA breach detection, list sorting, and historical trend charts") does not mention, because it lives in tenant data, not application code.

**How to avoid:**
- Before writing a single line of new scoring code, grep the schema for every column that stores a `risk_score`-shaped threshold as tenant data (`ticketing/rule_engine.py` conditions JSONB, `saved_filters` conditions JSONB) and enumerate every tenant row using one.
- Ship a migration report (not just a recompute) that shows, per tenant, "this saved filter/rule referenced `min_risk_score=X`; under the new model, the assets it now matches changed by N (+/-)" — require an admin acknowledgment or an explicit re-tuning UI before the rule goes live on the new score, rather than silently reinterpreting the same number.
- Consider whether `min_risk_score` thresholds should be automatically rescaled by a documented mapping function (old-percentile → new-percentile) rather than left as a raw number whose meaning silently shifted.
- Add an audit event when a rule's *effective match set* changes materially at cutover, even though the rule's stored condition itself didn't change — this is a "config drift underneath you" case the existing audit system was never built to detect.

**Warning signs:**
A migration plan that only touches `assets.risk_score` and `daily_snapshots.metrics` and doesn't mention `ticketing.rule_engine` conditions or `saved_filters`; a tenant complaint post-ship of "we suddenly got 40 new tickets overnight" or "our automation rule stopped firing."

**Phase to address:** Risk Model Rebuild phase (define the migration contract for tenant-authored thresholds as a first-class deliverable, not an afterthought) — verified by a pre/post match-set diff report run against every tenant's actual rules/filters before cutover, not just a schema migration test.

---

### Pitfall 2: Hardcoded Severity-Bucket Boundaries Are Duplicated Across the Codebase, Not Centralized

**What goes wrong:**
The critical/high/medium/low risk-score bucket boundaries (`>=80`, `50-79`, `20-49`, `<20`) are **hand-copied as magic numbers** into at least three independent files: `backend/app/export.py` (executive-summary bucket counts), `backend/app/assets/router.py` (stats endpoint), and `backend/app/vulnerabilities/dashboard.py` (dashboard tiles) — with no shared constant. If the new model's rebuild changes the scale (e.g., a 0–1000 raw exposure index, or a redefined 0–100 with a different distribution), updating one file and missing another produces a dashboard that says "12 critical assets" while the export PDF says "18 critical assets" for the same tenant at the same moment — a visible, embarrassing inconsistency in a product whose entire value proposition is a single trustworthy view.

**Why it happens:**
The thresholds were copy-pasted at three different feature-build times (dashboard, stats endpoint, export) with no central `RISK_TIERS` constant ever extracted, because each call site was built independently and the buckets "just needed to match the design system's 4-tier color language" at the time.

**How to avoid:**
- Before rebuilding the model, grep for every literal `>= 80`, `>= 50`, `>= 20` (and equivalents) anywhere near `risk_score`, and extract a single `RISK_TIER_BOUNDARIES` (or equivalent) constant that every consumer imports — this is a prerequisite refactor, not an optional cleanup.
- Make the new model's tier boundaries part of its own versioned definition (see Pitfall 3) so a future rescale only requires editing one place.
- Add a cross-endpoint regression test that asserts the dashboard tile counts, the stats endpoint counts, and the export bucket counts agree for the same seeded tenant — this test class doesn't exist today and would have caught this drift risk before it becomes visible in production.

**Warning signs:**
`grep -rn ">= 80\|>= 50\|>= 20" backend/app` returning more than one distinct call site tied to risk tiers; no single file owns "what does a risk score of 65 mean."

**Phase to address:** Risk Model Rebuild phase — the centralization refactor should land *before* the new formula, so there's exactly one place to change when the new tiers are defined.

---

### Pitfall 3: No Score-Model Version Tag Makes the Recompute Non-Idempotent and Non-Rollback-able

**What goes wrong:**
`Asset.risk_score` is a bare `Integer` with no companion `risk_model_version` (or `scored_at`, or formula-hash) column. `compute_risk_scores()` overwrites it in place, unconditionally, every time it's called (which is currently every connector sync). Once the new model ships and recomputes every asset, there is no way to tell — from the data alone — whether a given asset's current `risk_score` reflects the old formula, the new formula, or a half-finished migration; no way to detect "did the one-time recompute actually run for this tenant"; and no way to safely roll back to the old formula if the new one has a bug discovered post-ship, because the old score was overwritten with no backup.

**Why it happens:**
The existing scoring code was built as a pure "recompute the current truth" function — reasonable when there's only ever been one formula, but a clean-slate replacement needs the score to be provably attributable to a specific formula version, and that concept doesn't exist in the schema today.

**How to avoid:**
- Add `risk_model_version` (or equivalent) alongside `risk_score` in the same migration that introduces the new formula, and stamp every write (recompute and per-sync) with it — never leave it implicit.
- Before overwriting, snapshot the pre-migration `risk_score` per asset into a `risk_score_v1_backup` column or a dedicated migration-audit table, scoped by tenant, so a rollback is a data restore, not a re-derivation from history that may no longer be reconstructable (see Pitfall 9 — the source data needed to recompute the *old* formula may itself have been superseded by then).
- Make the recompute job itself idempotent and safely re-runnable: re-running it on an already-migrated tenant should be a no-op (or a cheap verify), not a second mutation — this is what makes partial-failure recovery (Pitfall 8) tractable.
- Treat the recompute as a migration with its own explicit success/failure state per tenant (a `risk_model_migrations` tracking table: `tenant_id`, `status`, `started_at`, `completed_at`, `assets_migrated`), not a fire-and-forget background call.

**Warning signs:**
No column anywhere named `*_version` near `risk_score`; the recompute function's only observable output is "assets_updated: N" with no way to distinguish "migrated to v2" from "already was v2" from "still v1."

**Phase to address:** Historical Recompute / Migration phase — this is the single most important prerequisite for that phase to be safe; do not build the recompute job until the version/tracking column exists.

---

### Pitfall 4: No Shadow/Comparison Period Means Old vs. New Score Divergence Is Never Actually Observed

**What goes wrong:**
The natural implementation path is: ship the new formula, run the one-time recompute, done. But nobody on the team — engineer or tenant admin — ever sees old-score-vs-new-score side by side for real production data before the old one is gone. If the new model has a subtle bug (e.g., double-counting a signal, an exposure-context multiplier that's miscalibrated, a sign error making internet-facing assets score *lower*), it ships silently, because there's no moment where both scores exist to be compared and sanity-checked against analyst intuition ("wait, why is our crown-jewel prod DB suddenly a 30?").

**Why it happens:**
"Clean slate, replace it" framing (explicitly the milestone's own language) discourages a dual-write/shadow period because it sounds like scope creep on a migration that's supposed to be one-time — but a one-time cutover with zero verification window is exactly how a bad formula reaches every tenant simultaneously with no safety net.

**How to avoid:**
- Compute the new score into a *shadow column* (e.g., `risk_score_v2_preview`) for at least one full sync cycle per tenant before flipping any consumer (SLA, sort, trend, automation rules) to read it — this costs one extra column and one extra write, not a parallel system.
- Build a diff report (reusable from Pitfall 1's tenant-threshold report): for each tenant, top-20 assets whose rank changed most between old and new, and any asset whose tier flipped by more than one bucket — have a human (even just the implementing engineer, ideally a design partner tenant) eyeball it before flipping the switch tenant-wide.
- Gate the actual cutover (the moment SLA/sort/trend/automation start reading the new column) behind an explicit flag per tenant, not a single global deploy — this also bounds blast radius if the formula does turn out to be wrong (see Recovery Strategies).

**Warning signs:**
A PR that adds the new formula and flips all consumers to it in the same commit; no "here's the diff report for tenant X" artifact anywhere in the phase's plans/verification; the only test is "the formula computes *a* number," not "the formula computes a *sane* number relative to the old one."

**Phase to address:** Risk Model Rebuild phase for the shadow-column mechanism; Historical Recompute / Migration phase owns running and reviewing the diff report per tenant before flipping consumers.

---

### Pitfall 5: Trend Charts and Risk-Spike Alerts Break Exactly at the Cutover Boundary

**What goes wrong:**
`backend/app/vulnerabilities/trends.py` stores `avg_risk_score` inside `daily_snapshots.metrics` (a JSONB blob captured once per day per tenant) and `get_risk_score_trend()` just plots that series over time — there is no concept of "the scale changed here." The moment the new model's recompute runs, every subsequent day's `avg_risk_score` is on a different scale (or distribution) than every prior day's, so the trend chart shows a vertical cliff (or an unexplained jump) on the cutover date that has nothing to do with actual security posture change. Worse, `backend/app/notifications/alerts.py::_check_risk_score_changes()` explicitly diffs **today's `Asset.risk_score` against yesterday's snapshot** and fires a "risk spike" notification for any asset whose score jumped ≥20 points — on cutover day, this will fire for a large fraction of the tenant's entire asset fleet simultaneously (because every asset's score changed due to the formula, not real risk), flooding tenants with false "risk change" alerts on the exact day they should be building confidence in the new model.

**Why it happens:**
Both the trend chart and the alert-delta logic were built assuming the score is a stable, continuously-comparable metric across time — a fair assumption when there's only ever been one formula, but false the instant that formula changes underneath already-stored historical data.

**How to avoid:**
- Record the cutover date/version boundary explicitly (ties to Pitfall 3's version column) and have the trend chart either (a) annotate the discontinuity visibly ("scoring model updated on this date — values before/after are not directly comparable") or (b) only render the new-model series going forward, with the old series available as a separate, clearly-labeled historical chart.
- Suppress or specially-flag `_check_risk_score_changes()` for the cutover day/window per tenant — a one-line guard ("skip delta-based alerting if either side of the comparison spans a model-version boundary") prevents an alert storm; this is cheap to add once Pitfall 3's version tracking exists and expensive to firefight after the fact.
- Do not silently recompute historical `daily_snapshots.metrics.avg_risk_score` retroactively to "smooth" the chart — that would fabricate history under the new formula for dates where the underlying enrichment signals (Pitfall 9-12) may not have existed yet, which is its own integrity problem.

**Warning signs:**
No code path checks `daily_snapshots.snapshot_date` against a model-version cutover date before diffing; a demo of the new model that never shows what the trend chart or the notifications feed look like on the day of cutover.

**Phase to address:** Risk Model Rebuild phase defines the version boundary; Historical Recompute / Migration phase must explicitly guard `_check_risk_score_changes()` and the trend chart rendering for the cutover window as part of its own completion criteria — not deferred as a "nice to have."

---

### Pitfall 6: A Cross-Tenant One-Time Recompute Job Bleeds Tenant Data if Not Explicitly Scoped

**What goes wrong:**
`compute_risk_scores(db, tenant_id)` already takes `tenant_id` as a required, scoped parameter — that discipline is correct today. But a *one-time historical migration* is a fundamentally different code path than "recompute this one tenant after its sync," and it will likely be written as a new top-level script/task ("for every tenant, recompute") rather than reusing the existing per-tenant function call site-by-site. The risk is a new migration entry point that queries `Asset`/`Vulnerability` globally (e.g., a raw SQL migration that does `UPDATE assets SET risk_score = ...` with a subquery that forgets to join back through `tenant_id`, or that computes an aggregate across all tenants' vulnerabilities by CVE ID before per-asset attribution) — a classic multi-tenant migration bug: code that's correct in the steady-state ORM path gets rewritten "for performance" as a bulk SQL operation for the one-time job, and the rewrite drops the tenant boundary that the ORM version enforced implicitly.

**Why it happens:**
One-time migrations are almost always written under time pressure as "just get all the data right once," and engineers reach for bulk SQL (for both speed and to avoid loading everything into Python) — exactly the style of code most likely to accidentally cross a `WHERE tenant_id = ...` boundary that the everyday, per-request ORM code never has to think about because FastAPI dependency injection already scopes it.

**How to avoid:**
- The one-time recompute must be built by **iterating the existing per-tenant `compute_risk_scores(db, tenant_id)` call** (or its v2 successor) once per tenant in a loop, not by writing a new cross-tenant bulk-SQL migration — reuse the already-tenant-scoped function, don't reinvent a global one.
- If any part of the new enrichment/exposure-context computation genuinely needs a cross-tenant lookup (e.g., a shared EPSS/KEV reference table — which is legitimately tenant-agnostic, unlike risk scores), keep that lookup in a clearly-separate, read-only, tenant-agnostic path and never let it write to a tenant-scoped table without re-applying the `tenant_id` filter at the write.
- Extend GetVul's existing tenant-isolation regression-test pattern (already used for source-filter regression in PROD-04 and for the v3.0 AI cache) to the new recompute job specifically: seed two tenants with overlapping CVE IDs/hostnames, run the migration, assert neither tenant's `risk_score` was influenced by the other's data.
- Run the migration tenant-by-tenant with per-tenant commit boundaries (ties to Pitfall 8) — this also naturally limits the blast radius of a tenant-bleed bug to one tenant's transaction if the isolation test is skipped and the bug ships anyway.

**Warning signs:**
A migration script with a single `UPDATE ... FROM (SELECT ... GROUP BY cve_id)` (no `tenant_id` in the `GROUP BY`/`WHERE`) instead of a per-tenant loop; a migration PR with no cross-tenant isolation test attached; "run once for all tenants" framing in the migration's own docstring with no per-tenant scoping visible in the query itself.

**Phase to address:** Historical Recompute / Migration phase — this is a hard blocking requirement, not a nice-to-have; verified by a live two-tenant isolation regression test, not just a code-review read-through.

---

### Pitfall 7: The Recompute Pegs the Single VM and Starves the In-Process Scheduler Tick

**What goes wrong:**
`compute_risk_scores()` today already does a **per-asset Python loop issuing an individual `UPDATE` statement per row** (not a single bulk `UPDATE ... FROM` statement) — acceptable at today's scale and call frequency (once per connector sync), but the new model adds joins against enrichment JSONB, per-source native-signal columns, and exposure-context fields, making each iteration heavier. `backend/app/connectors/scheduler.py`'s `_scheduler_loop()` is a **single asyncio event loop** that, every 60 seconds, sequentially runs connector-due checks, ticket rule evaluation, scheduled reports, SLA backfill/breach checks (`await`ed inline, not dispatched), daily ticket sync, snapshot capture, notification alert checks, and AI batch prewarm/poll dispatch — all in the same process as the FastAPI app serving live requests. A one-time recompute that touches every asset for every tenant, run naively (one big transaction, or dispatched without yielding control back to the loop), will either (a) hold a single long-running DB transaction that blocks other writes on a single-Postgres-instance deployment, or (b) if run as a long synchronous stretch of Python inside the same asyncio loop as the scheduler, delay every other scheduled tick (SLA breach detection, ticket sync, AI batch dispatch) for the duration — on a single VM with no worker pool to absorb it, this is directly user-visible (sync ticks stall, SLA breaches stop being detected on time, the dashboard the analyst has open goes momentarily stale).

**Why it happens:**
The existing code already normalizes to "recompute is cheap, just call it inline" because today it only touches the tenant that just synced. A historical, all-tenants, richer-formula recompute is an order of magnitude more expensive per call and touches every tenant at once — but nothing in the architecture forces anyone to notice that scaling change until it's running in production during the actual migration.

**How to avoid:**
- Convert the per-asset Python-loop `UPDATE` to a single bulk `UPDATE ... FROM (subquery)` statement (Postgres supports this directly) for both the steady-state per-sync recompute and the one-time migration — this is a prerequisite performance fix, not migration-specific, since the new model's added joins make the existing pattern strictly worse even in steady state.
- Run the one-time migration as an explicit, throttled, chunked job (batch of N assets or one tenant at a time) with a deliberate `await asyncio.sleep(0)` (or short sleep) between chunks so the event loop can service other pending tasks — never run it as one unbroken synchronous stretch.
- Run it **outside** the scheduler's own tick cycle (a separate one-shot admin CLI/script invocation at deploy time — the pattern GetVul already uses for `python -m app.encryption rotate`), not folded into `_scheduler_loop()`'s per-tick work, so a single slow migration run can't compound with every other scheduled duty in the same tick.
- Load-test the migration against a seeded fixture sized to the largest realistic single-VM tenant fleet (thousands of assets, tens of thousands of findings) before ship, measuring both wall-clock time and — critically for this deployment model — whether concurrent live requests (dashboard load, an analyst opening a drill panel) show measurably increased latency while it runs.
- Consider a maintenance-mode banner or a "recompute in progress" indicator for the affected tenant, so degraded responsiveness during the one-time migration is communicated rather than silently experienced as the app being slow.

**Warning signs:**
The migration's own runtime is untested against realistic asset/finding counts; the migration reuses `compute_risk_scores()`'s existing per-row `UPDATE`-in-a-Python-loop pattern unchanged (verify by reading the actual join/update shape, not just "it says risk_score" in a diff); no throttling/chunking/yield points visible in the migration code; the migration is invoked via `trigger_background_sync`-style `asyncio.create_task` dispatch inside the scheduler rather than a standalone script.

**Phase to address:** Historical Recompute / Migration phase — the bulk-`UPDATE` refactor and chunked/throttled execution model are launch-blocking requirements for this phase specifically, verified with a load test against a realistic fixture, not just correctness tests on a handful of seed rows.

---

### Pitfall 8: Partial-Failure Recompute Leaves a Tenant With Mixed Old/New Scores and No Resume Point

**What goes wrong:**
If the one-time recompute is interrupted mid-run (a container restart during a deploy, a Postgres connection blip, an unhandled exception on one malformed asset row) without the version-tracking column from Pitfall 3, there is no way to tell which of a tenant's assets got the new formula and which are still on the old one — and every downstream consumer (sort, SLA, tickets, dashboard tiles) will silently mix both populations in the same list, producing a genuinely nonsensical sort order (some assets ranked by the old scale, some by the new) that's far worse than either scale alone.

**Why it happens:**
`compute_risk_scores()`'s current error handling is "the whole function either completes or throws" with no per-asset checkpointing — fine for a fast, idempotent, single-tenant recompute triggered on every sync (a failure just means it'll retry cleanly on the next sync), but dangerous for a slow, one-time, must-not-repeat-side-effects migration where a partial run is a distinct, worse state than either "not started" or "complete."

**How to avoid:**
- Make the migration resumable at the asset (or tenant) granularity: mark each asset (or tenant) with its `risk_model_version` as it completes (Pitfall 3), so a re-run of the migration script is a cheap "skip anything already on v2" pass, not a re-derivation from scratch — this also directly enables safe re-runs after any interruption.
- Never let a single malformed row (missing enrichment field, unexpected JSONB shape) abort the entire tenant's batch — catch and log per-asset failures, continue the batch, and surface a post-run report of "N assets could not be migrated, still on v1" rather than silently rolling back or silently leaving them un-flagged.
- Add a tenant-level dashboard/admin surface (or at minimum a structured log line + a query an operator can run) showing "this tenant is mid-migration: X/Y assets on v2" — during a mixed state, sort/SLA/trend consumers should ideally be gated to keep reading v1 consistently for that tenant until 100% of its assets are migrated, rather than reading a shifting mixed population query-by-query.
- Wrap each tenant's migration in its own transaction (or its own small-batch transactions) rather than one transaction spanning every tenant — a failure for tenant B should never roll back or block tenant A's already-committed migration.

**Warning signs:**
No idempotency check before re-running the migration ("did this asset already get migrated?"); a migration script that wraps the entire multi-tenant run in one top-level `try/except` with no per-asset or per-tenant granularity; no operator-visible way to answer "is tenant X fully migrated right now."

**Phase to address:** Historical Recompute / Migration phase — resumability and per-tenant/per-asset failure isolation are part of this phase's core deliverable, verified by an explicit "kill the migration mid-run and re-run it" test, not just a happy-path run.

---

### Pitfall 9: Every Connector Already Ad Hoc Flattens Native Signals Into Booleans — the Milestone Must Undo This, Not Just Add to It

**What goes wrong:**
The milestone's stated goal is to "preserve scanner-native signals (ExPRT.AI, VPR, EPSS/exploitability, threat-intel) currently normalized away" — but this normalization is not a single choke point to fix, it's **six independent, already-shipped, inconsistent implementations**:
- `crowdstrike.py` derives `exploit_available = exploit_status_id >= 20` (PoC-or-higher) and `cisa_kev = exploit_status_id >= 50 OR cve_meta.cisa_kev` — CrowdStrike's actual ExPRT.AI rating (which almost certainly has more than two meaningful tiers — no-exploit / PoC / functional / weaponized / actively-exploited) is collapsed to two booleans at ingestion, and the raw `exploit_status_id`/tier name is not persisted anywhere.
- `defender.py` sets `exploit_available = exploitVerified OR publicExploit` and **hardcodes `cisa_kev=False` unconditionally** — Defender-sourced findings can never be flagged as CISA KEV in this codebase today, regardless of the actual CVE's KEV status.
- `nessus.py` derives a boolean from a sub-attribute string check (`"true"/True/"1"`) — Nessus's actual **VPR** (Vulnerability Priority Rating, a continuous 0–10 score distinct from CVSS) is never captured; the `epss_score` column that already exists on `Vulnerability` is **not populated by any connector today** (verified: zero matches for "epss" across all six connector files) — it's a dead column.
- `rapid7.py` collapses an actual exploit *count* (`exploit_count > 0`) to a boolean, discarding the count.
- `wiz.py` and `qualys.py` each have their own independent boolean-derivation heuristics with different source fields and thresholds.

If the enrichment phase adds new native-signal columns/JSONB but leaves these six ingestion paths untouched, the new fields will be **null/empty for every finding ingested before the enrichment phase shipped**, and *inconsistently populated going forward* per-connector (some scanners genuinely don't expose an ExPRT.AI-equivalent tier; that's a real absence, not a bug — but it looks identical, in the data, to "this connector's ingestion code just wasn't updated yet").

**Why it happens:**
Each connector was built independently over time by different phases/executors, each making a locally-reasonable call about how to represent "is this exploitable" as a single boolean for the (at-the-time) single risk-score formula that only needed a boolean. Nobody was asked to preserve the richer native value because nothing downstream consumed it — until now.

**How to avoid:**
- Treat "add the new signal to the schema" and "make every connector's ingestion code actually populate it from the raw vendor payload" as two separate, both-mandatory deliverables — a schema migration alone changes nothing if `crowdstrike.py` doesn't also start writing the real ExPRT.AI tier into it.
- Go back to each connector's actual raw API response (not the already-collapsed `VulnRecord`/`base.py` intermediate dataclass) to find the native field, since the current intermediate representation (`exploit_available: bool`, `cisa_kev: bool` in `connectors/base.py`) is itself the point where richness was already lost — the new enrichment fields need to be threaded through from the vendor payload, not derived from the already-boolean-ized dataclass.
- Fix the Defender `cisa_kev=False` hardcode as part of this work — it's a pre-existing correctness bug this milestone's own goals expose, not just a missing-enrichment gap.
- Populate (or explicitly and visibly deprecate) the already-dead `epss_score` column rather than adding a second, redundant EPSS-like field next to an unused one.
- Build one small conformance test per connector asserting "a known fixture payload with a known native signal value produces the expected preserved field" — six connectors means six independent chances to get the mapping wrong, and a shared test harness catches drift across all of them consistently.

**Warning signs:**
A migration adds new columns (`exprt_tier`, `vpr_score`, etc.) but `git diff` shows no changes to any of the six connector files' parsing logic; the new fields are consistently `NULL` for a spot-check of recently-synced findings; the Defender `cisa_kev=False` hardcode is untouched.

**Phase to address:** Connector Enrichment phase — this must include per-connector ingestion rewrites, not just a schema addition; verified by a fixture-based conformance test per connector, not a single generic "the field exists" test.

---

### Pitfall 10: A Missing Native Signal Is Not the Same as a Negative One

**What goes wrong:**
Once native signals (ExPRT.AI tier, VPR, real KEV status) are captured per-source, the new risk model — and any UI badge/filter built on top — must distinguish "this scanner reported no exploit" from "this scanner doesn't tell us about exploits at all" (or, per Pitfall 9's Defender example, "this connector hasn't been updated to report it yet"). If the new model treats a `NULL`/absent native signal the same as an explicit "not exploitable" (e.g., defaulting a missing VPR to 0, or a missing ExPRT tier to "no exploit"), assets whose *only* scanner coverage is a source that doesn't emit that particular signal will be systematically **under-scored** relative to assets covered by a richer-signal scanner — not because they're actually safer, but because of which tool happened to see them.

**Why it happens:**
Numeric defaults are the path of least resistance in a scoring formula ("if vpr_score is None, treat as 0") and the bug is invisible without deliberately testing a finding from a signal-poor source against one from a signal-rich source at otherwise-identical severity.

**How to avoid:**
- Model absence explicitly in the formula (e.g., a per-signal "known/unknown" flag feeding a neutral-weight fallback, not a zero-weight one) rather than relying on a numeric default that happens to mean "no risk contribution."
- Document, per connector, exactly which native signals it can and cannot supply (a capability matrix), and surface that gap in provenance badges/tooltips ("Nessus: VPR available; Defender: KEV status not reported by this connector") rather than presenting silence as a confirmed negative.
- Add a test asserting that a CRITICAL finding from a signal-poor-only source scores comparably (not lower) to an identical CRITICAL finding from a signal-rich source, all else equal.

**Warning signs:**
A scoring formula with `signal_value or 0` / `signal_value or default` patterns without an explicit presence check; assets whose only coverage is Defender (today, permanently `cisa_kev=False`) scoring systematically lower on any KEV-weighted dimension than functionally-identical CrowdStrike/Wiz-covered assets.

**Phase to address:** Risk Model Rebuild phase (formula design) with a conformance check owned jointly by the Connector Enrichment phase (documenting per-connector signal availability).

---

### Pitfall 11: JSONB Enrichment Schema Drifts Silently Across Six Independent Connectors, and the Existing Correlation Table Is Already Hardcoded to Only Four Sources

**What goes wrong:**
Two compounding structural risks:
1. If per-connector native signals are stored in a shared JSONB column (e.g., `Vulnerability.native_signals` or similar) rather than typed columns, each connector will naturally shape its own sub-object differently (different key names, nesting, value types for conceptually-equivalent data) unless a shared schema contract is enforced — a filter or badge built against "the first connector's shape" silently breaks or shows nothing for the other five.
2. This is not hypothetical: `backend/app/vulnerabilities/correlation_service.py`'s `VulnerabilityCorrelation` model and its `SOURCE_COLUMN_MAP` **already only has four hardcoded columns** — `crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id` — with **no `qualys_vuln_id` or `rapid7_vuln_id` column at all**, even though `VulnSource` has included `QUALYS` and `RAPID7` since v1.0 Phase 4. `_find_correlated_groups()` correctly *counts* all sources (it groups by `Vulnerability.source` generically), so `sources_count` can legitimately be 3 for a Qualys+Rapid7+Wiz correlation — but the `values` dict built in `run_correlations()` only extracts the four mapped keys via `.get()`, so a Qualys or Rapid7 vuln ID is silently dropped from the persisted row. `get_correlation_for_vuln()` then reconstructs its `sources` list by checking only those same four ID columns — meaning **a correlation with `sources_count=3` (Qualys+Rapid7+Wiz) would report a `sources` list containing only `["WIZ"]`** to any caller, including whatever builds provenance badges. This is a live, current, verifiable schema-hardcoding bug, not a hypothetical risk, and it is exactly the substrate the new provenance-badge/source-filter features need to be correct.

**Why it happens:**
The correlation table was built when only four connectors existed; Qualys/Rapid7 were added later (v1.0 Phase 4) as *vulnerability ingestion* sources without anyone revisiting the correlation schema's hardcoded per-source columns, because nothing at the time depended on correlation-level provenance being complete for those two sources.

**How to avoid:**
- Before building source-provenance badges or filters, fix `VulnerabilityCorrelation` to either (a) add `qualys_vuln_id`/`rapid7_vuln_id` columns (minimal fix, same hardcoded-per-source pattern, needs a schema migration every time a 7th scanner is added), or (b) refactor to a normalized `correlation_sources` join table (`correlation_id`, `source`, `source_vuln_id`) that scales to N sources without a schema migration per new connector — given this milestone explicitly wants source-awareness to be a durable, filterable, badge-driving dimension going forward, the normalized table is the right investment now rather than repeating the four-column pattern with two more hardcoded columns.
- For any new enrichment JSONB, define and enforce a shared Pydantic schema for the native-signals sub-object that every connector must conform to (reuse the existing `VulnRecord` dataclass discipline in `connectors/base.py` as the pattern to extend, not bypass) rather than each connector free-forming its own JSON shape.
- Add a regression test asserting `get_correlation_for_vuln()`'s returned `sources` list length always equals `sources_count` — this single assertion would have caught the existing Qualys/Rapid7 gap immediately and should be a permanent guard against the same drift recurring for a future 7th/8th scanner.

**Warning signs:**
`grep -n "SOURCE_COLUMN_MAP" backend/app/vulnerabilities/correlation_service.py` showing fewer entries than `VulnSource` has values; a provenance badge or source filter that never shows "Qualys" or "Rapid7" as a contributing source on any multi-source-correlated finding, even when seed data clearly includes both.

**Phase to address:** Connector Enrichment phase (or an explicit prerequisite step within it) must fix the correlation schema gap before the Provenance Badges phase builds on top of it — verified by the `sources_count == len(sources)` regression test plus a live seed-data check that a Qualys+Rapid7-only correlation surfaces both source badges correctly.

---

### Pitfall 12: EPSS/KEV Signals Go Stale With No Refresh Cadence

**What goes wrong:**
EPSS scores are explicitly designed to be recalculated daily (FIRST.org publishes a new EPSS model output every day), and the CISA KEV catalog is updated on an ongoing basis as new exploited CVEs are confirmed. If the new risk model treats a captured EPSS/KEV value as a point-in-time fact set once at ingestion (only refreshed on the next full connector sync, whenever that happens to be — `sync_interval_minutes` is per-connector-configurable and could be daily, weekly, or longer for a lower-priority connector), a CVE that gets added to KEV *today* won't affect the risk score of an already-ingested finding until that finding's source connector happens to re-sync and re-report it — potentially a meaningful lag for a signal whose entire value proposition is "this is now being actively exploited, treat it as urgent right now."

**Why it happens:**
EPSS/KEV values arrive bundled with the rest of a scanner's per-finding payload during a sync, so it's natural to treat them as "just another field on this row" refreshed on the same cadence as everything else about that finding — but their *temporal* nature (a daily-refreshed external feed, not a property of the finding itself) is different from CVSS or the finding's own status.

**How to avoid:**
- Treat EPSS/KEV as their own independently-refreshed reference data (a small per-CVE lookup table refreshed on its own daily cadence, decoupled from any individual connector's sync interval) rather than a field that only updates when a specific scanner happens to re-report a specific finding — this also naturally solves cross-connector consistency (the same CVE seen by two scanners should show the same EPSS/KEV value, not two independently-stale copies).
- If a dedicated EPSS/KEV refresh job is out of scope for this milestone (no direct FIRST.org/CISA feed ingestion planned), at minimum document the staleness bound explicitly in the exposure-context and score documentation ("KEV/EPSS reflects the value at last scanner sync, which may lag the live feed by up to N days") so the score's precision isn't oversold, and consider surfacing a "last verified" timestamp on any KEV/EPSS-driven risk contribution in the UI.
- Whatever the choice, make it a deliberate one recorded in Key Decisions — this is the kind of ambiguity that otherwise gets resolved implicitly and inconsistently by whichever engineer touches the code first.

**Warning signs:**
No scheduled job or reference table anywhere for EPSS/KEV independent of connector sync; a demo where a well-known actively-exploited CVE with a stale ingested `cisa_kev=False` doesn't get flagged until the next full sync of whichever connector originally reported it.

**Phase to address:** Connector Enrichment phase should scope this explicitly as an open decision (build a refresh job vs. document the staleness bound) rather than let it default silently to "refreshed whenever the connector happens to resync."

---

### Pitfall 13: Auto-Inferred Exposure Context Overrides or Silently Conflicts With Existing Analyst-Set Tags

**What goes wrong:**
GetVul already has an informal mechanism for exactly this concept: `Asset.tags` (a free-text `ARRAY(String)`, e.g., `["pci", "internet-facing", "dmz", "tier-1"]`) that analysts set manually today, and which the v3.0 AI remediation prompt already treats as meaningful exposure context ("Tagged internet-facing and in PCI scope..."). The new milestone introduces *formal*, typed, auto-inferred fields (criticality / data-sensitivity / internet-facing) with admin override — but if this is built as an entirely separate mechanism from `tags`, an asset can end up with **two contradictory sources of truth for the same concept** (an analyst's existing `"internet-facing"` tag vs. an auto-inferred `internet_facing=False` field), with no reconciliation and no clear precedence rule for which one the new risk model or SLA logic should actually trust. Worse, if the auto-inference process is ever built to *write* to `tags` as a side effect (a plausible-seeming shortcut — "just add the inferred label as a tag too"), it risks silently overwriting or duplicating analyst-authored labels that were deliberately curated (e.g., a manually-added `"tier-1"` designation that has organizational meaning beyond what any auto-inference heuristic could know).

**Why it happens:**
`tags` already does 80% of what "exposure context" conceptually is, built organically for a different, more general purpose (any operational label) — it's tempting to either (a) treat the new formal fields as fully independent and never look at `tags`, missing analyst intent already captured there, or (b) conflate them and have auto-inference silently mutate `tags`, corrupting an existing analyst-curated data source.

**How to avoid:**
- Explicitly design the precedence rule before writing inference code: admin override (once set) always wins over auto-inference, permanently, until explicitly cleared — never silently re-inferred over on the next sync. This must be enforced at the query/write layer (a `criticality_source: "auto" | "override"` discriminator column, not just "the field has a non-null value" — a `null` override is ambiguous with "never set" vs. "explicitly cleared back to auto").
- On first rollout, treat existing `tags` values as a *migration input* to seed initial exposure-context fields (e.g., a `tags` entry matching `"internet-facing"`/`"pci"`/`"tier-1"` patterns should inform — not be silently ignored by — the first auto-inference pass), rather than starting the new fields from a blank slate that contradicts what analysts already told the system.
- Never have auto-inference write back into `tags` — keep the free-text operational-label array and the new typed exposure-context fields as clearly separate concerns with a one-directional migration path (tags informed the initial seed) rather than an ongoing bidirectional sync that can silently clobber either side.
- Surface, in the UI, *why* a value was auto-inferred (which signals drove it) and make override a first-class, audited action (ties to the milestone's constraint that new mutating actions require audit events) — an analyst who disagrees with an inference needs both visibility into its reasoning and a trusted way to correct it permanently.

**Warning signs:**
Two competing "is this internet-facing" answers visible for the same asset (a `tags` entry and a typed field) with no UI indication of which one is authoritative; an override that gets silently reset back to an auto-inferred value on the next connector sync (a sign the override isn't actually being read before the auto-inference write path runs); no audit log entry for a criticality override action.

**Phase to address:** Exposure Context phase — the precedence/discriminator design and the tags-as-migration-seed decision must be resolved before any inference heuristic is written, verified by a test that sets an override, re-runs auto-inference, and asserts the override is untouched.

---

### Pitfall 14: Criticality Inflation Cascades Silently Into SLA and Score Distortion

**What goes wrong:**
Once asset criticality auto-inference exists and feeds the new risk model (and, per the milestone's own framing, SLA breach detection depends on the new model), there's a strong incentive — for both the auto-inference heuristic and any admin using the override — to over-mark assets as "critical" ("better safe than sorry"), especially if the inference heuristic is tuned defensively (e.g., "any ambiguous signal defaults to higher criticality"). If criticality tightens SLA windows or amplifies risk-score weighting, criticality inflation directly means SLA breaches trigger sooner/more often across a growing share of the fleet, drowning the exact prioritization signal the whole rebuild exists to sharpen — the SLA/ticket-automation system starts treating everything as urgent, which functionally means it stops distinguishing anything as urgent.

**Why it happens:**
Auto-inference heuristics built from limited signals (MDM/HR enrichment + scanner flags) will have real uncertainty, and the "safe" failure mode — treating uncertain cases as more critical rather than less — feels responsible in isolation but is systemically corrosive once criticality is load-bearing for SLA timing and score weighting across an entire fleet, not just a single asset's display badge.

**How to avoid:**
- Calibrate and cap the *proportion* of assets the auto-inference heuristic can mark as highest-criticality tier — if a heuristic run classifies, say, 60% of a tenant's fleet as "critical," that's a signal the heuristic (or its defaults) is miscalibrated, not that the tenant genuinely has that profile; surface this as a sanity-check metric during the Exposure Context phase's own testing, not discovered later via SLA-metric anomalies.
- Make the inference's confidence explicit (not just a boolean criticality flag) and let low-confidence inferences carry less weight in the risk formula than a high-confidence signal or an explicit admin override — this also directly supports Pitfall 13's UI transparency goal.
- Track, post-ship, the tenant-wide SLA-breach rate and ticket-automation-rule fire rate before and after exposure-context rollout (reusing the diff-report instinct from Pitfall 1/4) — a sharp increase with no corresponding real change in vulnerability posture is the direct symptom of criticality inflation and should trigger a heuristic review, not be treated as "the new model is just more sensitive."

**Warning signs:**
A criticality-inference heuristic with no calibration/proportion sanity check run against real seed/production-like data before ship; SLA breach counts or automation-rule ticket-creation volume spiking tenant-wide shortly after the exposure-context rollout with no corresponding spike in actual new vulnerabilities.

**Phase to address:** Exposure Context phase owns the calibration sanity-check; Risk Model Rebuild phase (or its verification) should track SLA/automation-volume metrics pre/post rollout as an explicit guardrail.

---

### Pitfall 15: "Source" Means a Structurally Different Thing on Each of the Four Screens — OR/AND Semantics and Double-Counting Break at the Boundaries

**What goes wrong:**
The milestone wants scanner-source filtering (OR default + AND toggle) across Vulnerabilities, Assets, CSPM, and Tickets — but these four entities represent "source" with **four genuinely different data shapes** in the current schema, verified directly:
- **Vulnerabilities**: each row has its own `source` column (one scanner per row), PLUS a separate `VulnerabilityCorrelation` table that links multiple same-CVE-same-asset rows across sources (with the Pitfall 11 gap). A naive "filter vulnerabilities by source" is a simple `source IN (...)` on the row itself; but "AND: show only vulns confirmed by 2+ selected sources" requires querying through the *correlation table*, not the vulnerability row — a structurally different query path, and if a caller filters the base `vulnerabilities` table by `source IN (X, Y)` for the AND case, they will get **two separate rows** (one from X, one from Y) rather than one de-duplicated, cross-source-confirmed finding — a correlated CVE-on-asset displayed/counted twice instead of once. This is the double-counting risk named in the question, and it is a direct consequence of the existing schema shape, not a hypothetical edge case.
- **Assets**: source is `seen_by_sources`, a JSONB array already used via `.contains([s])`, but that array is **shared between vulnerability scanners (CROWDSTRIKE, NESSUS, etc.) and non-scanner enrichment sources (JAMF, HUMAANS, INTUNE)** — a scanner-source filter chip bar built naively off this field's full distinct-value set will surface HR/MDM sources as if they were scanner options, confusing "which scanner found vulnerabilities on this asset" with "which system enriched this asset's metadata."
- **CSPM (Misconfiguration)**: has only a per-row `source` column with **no correlation table at all** — unlike Vulnerabilities, there is no existing substrate for "this misconfiguration was confirmed by 2+ CSPM tools." An AND toggle here needs a genuinely new correlation concept (e.g., group by `rule_id`/`resource_id` across sources) built from scratch, not reused from the Vulnerabilities pattern, even though the milestone names all four screens as if the filter behaves uniformly.
- **Tickets**: have **no source column at all** — a ticket's "source" is only meaningful transitively, through whichever vulnerability/CVE it's about (via `ticket_vulnerabilities` or similar linkage) and that vulnerability's own `source`/correlation. Filtering tickets by scanner source therefore requires a join through to vulnerabilities, and a ticket referencing a *correlated, multi-source* finding needs a defined rule for whether it matches an AND filter on "sources A and B" (does a ticket about a Vuln that's OR-linked to A and B count? What if the ticket covers multiple vulns from different sources?).

**Why it happens:**
The milestone's framing ("source filtering across Vulnerabilities, Assets, CSPM, Tickets" with one OR/AND toggle description) reads as if it's one filter mechanism reused four times — but the actual data model has four incompatible shapes for what "source" means, built independently over multiple milestones by different teams/phases, and nothing in the existing schema unifies them.

**How to avoid:**
- Design the OR/AND semantics **per entity**, explicitly, rather than assuming one query pattern ports across all four — document, for each of the four screens, exactly what "AND: findings confirmed by source A and source B" resolves to at the query level (correlation-table join for Vulnerabilities; a new resource+rule_id grouping for CSPM; a `seen_by_sources` array-contains-all check restricted to the scanner subset for Assets; a join-through-to-vulnerability-correlation for Tickets).
- Fix Pitfall 11 (the correlation table's hardcoded/incomplete source columns) before building the Vulnerabilities AND-filter on top of it, or the AND toggle will inherit the existing Qualys/Rapid7 undercount.
- For Assets, explicitly partition `seen_by_sources` (or introduce a new field) so the scanner-source filter chip bar only ever offers the `VulnSource` enum values, never JAMF/HUMAANS/INTUNE — don't derive the filter's option list from "distinct values seen in the array" without that restriction.
- For CSPM, decide explicitly whether building a misconfiguration-correlation concept is in scope for this milestone or whether the AND toggle there is deferred/simplified (e.g., "AND" meaning "this resource has findings from both sources," not "this specific finding is confirmed by both") — and document that difference in the UI copy so analysts don't assume CSPM's AND behaves identically to Vulnerabilities' AND.
- For Tickets, define the transitive-source rule explicitly (e.g., "a ticket matches a source filter if any of its linked vulnerabilities' sources match") and test it against a ticket linked to a multi-source-correlated vulnerability specifically, since that's exactly the case most likely to double-count or behave unexpectedly.
- Write one regression test per entity, seeded with a genuinely multi-source-correlated example, asserting the OR count and the AND count are both what an analyst would actually expect (not just "the query runs").

**Warning signs:**
A single shared "source filter" query helper reused unmodified across all four routers; a demo where filtering Vulnerabilities by "CrowdStrike AND Nessus" returns a count higher than the number of distinct assets/CVEs actually seen by both (a sign of the double-count-via-un-deduplicated-rows failure mode); a CSPM source-filter chip bar with no AND toggle at all discovered only during implementation because "there's no correlation table for that."

**Phase to address:** Source Filtering phase — each entity's semantics should be an explicit, separately-reviewed design decision (and the Vulnerabilities case blocked on Pitfall 11's fix), verified by one multi-source-seeded regression test per entity, not a single generic filter test.

---

### Pitfall 16: Provenance Badges Imply Independent Confirmation When Only One Scanner Actually Saw the Finding, and Live Badge Computation Gets Expensive Once Correlation Fan-Out Is Real

**What goes wrong:**
A "source provenance badge" on a finding row is a strong implicit trust signal to a triage analyst — "multiple tools agree this is real" reads as higher-confidence than "one tool flagged this." Two distinct failure modes:
1. **Overclaiming confirmation**: if the badge UI doesn't clearly distinguish "reported by 1 scanner" from "confirmed by 2+ scanners" (e.g., showing the same visual weight/style for both, or showing a single scanner's logo with no count/tier indicator), an analyst may treat a single-source finding as more corroborated than it is — directly undermining the "true multi-scanner corroboration" value proposition the AND toggle is supposed to deliver. This is compounded by the existing `VulnerabilityCorrelation.confidence` tiers (HIGH ≥3 sources, MEDIUM =2, LOW... but LOW is only assigned when `sources_count < 2`, i.e., correlation rows are only created for 2+ sources at all per `_find_correlated_groups()`'s own filter — meaning single-source findings have **no correlation row and no confidence tier whatsoever**, they're just a bare `Vulnerability` row). A badge that only reads from the correlation table will correctly show single-source findings as unbadged/plain — but if a future iteration "helpfully" defaults an unbadged finding to some visual treatment that reads as neutral-to-positive rather than explicitly "single-source, unconfirmed," the distinction erodes.
2. **Performance at scale once badges are computed live**: if provenance badges are computed by querying the correlation table (or a per-finding join) live, per row, on every list render — rather than reading a pre-materialized field on the finding itself — list pages showing hundreds of findings will multiply into N+1 correlation lookups per page load; this compounds with the Pitfall 11 fix (a normalized `correlation_sources` join table is more N+1-prone than four flat columns unless queried with a proper batched join/aggregation).

**Why it happens:**
Provenance badges are visually simple ("show the scanner logos"), so it's easy to under-invest in the confidence-tier distinction in the UI design, and easy to reach for "just query the correlation table per row as we render" rather than designing the list query to fetch provenance in the same batched query as the findings themselves (mirroring how GetVul's existing `PerSourceStatusStrip` primitive already batches per-source data rather than querying per-row).

**How to avoid:**
- Make the single-source vs. multi-source-confirmed distinction visually unambiguous by design from the start (reuse the existing `Confidence` enum's HIGH/MEDIUM tiers, and add an explicit "unconfirmed / single source" visual treatment for the case with no correlation row at all — don't leave that case as an implicit, undesigned default).
- Fetch provenance data for a list page in the same batched query as the findings (a `LEFT JOIN` or a single follow-up query keyed by the page's finding IDs), never as a per-row live lookup inside a render loop — this is the same batching discipline the codebase already applies elsewhere (e.g., `PerSourceStatusStrip`, faceted counts in the Vulnerabilities list).
- Once Pitfall 11's fix lands (whichever schema shape is chosen), specifically load-test the provenance-badge query against a seeded fixture with realistic correlation fan-out (many assets, many CVEs, a meaningful fraction cross-source-correlated) as part of this phase's own completion criteria, not deferred to a general performance pass.
- Copy-review the badge/tooltip language explicitly for "confirmed by N sources" vs. "reported by 1 source" — this is a copy-voice decision (per this codebase's existing copy-voice discipline) as much as a visual one, and should be treated with the same rigor as any other user-facing trust signal.

**Warning signs:**
A badge component with no distinct visual state for single-source vs. multi-source-confirmed; a list-page query plan showing one correlation lookup per rendered row rather than one batched query for the whole page; no load test exists for the provenance query against a fixture with real correlation fan-out.

**Phase to address:** Provenance Badges phase — both the visual-confidence-tier design and the batched-query performance requirement are launch-blocking for this phase, verified by a load test against a realistically-correlated fixture and a design review confirming the single-source case has its own explicit, non-neutral-reading visual treatment.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Reuse `compute_risk_scores()`'s per-row Python-loop `UPDATE` pattern unchanged for the new, heavier formula | No refactor needed to ship the new formula quickly | Directly causes Pitfall 7 (VM pegging) once the formula does more joins per asset at recompute-everything scale | Never past the Historical Recompute phase's own load test |
| Ship the new score without a `risk_model_version` column "to keep the migration simple" | One fewer column/migration | Makes the recompute non-idempotent, unauditable, and unrollbackable (Pitfall 3) — the single most expensive omission to retrofit after cutover | Never |
| Add new enrichment columns/JSONB without rewriting the six connectors' ingestion parsing | Schema ships fast, "enrichment support" can be marked done | Fields are silently null/inconsistent forever for pre-migration and under-instrumented connectors (Pitfall 9) — indistinguishable from a real absence | Never — the schema and the six ingestion rewrites must ship together |
| Fix only the Vulnerabilities correlation table's source-column gap and leave CSPM's non-existent correlation concept for "later" | Vulnerabilities AND-toggle ships on schedule | CSPM's source filter/AND toggle either ships with silently different (weaker) semantics or gets rushed later without the same design rigor (Pitfall 15) | Acceptable only if explicitly scoped out and documented in the roadmap, not discovered mid-implementation |
| Let auto-inferred exposure context write into the existing `tags` array as a convenience | No new UI surface needed immediately | Corrupts analyst-curated tag data and creates two competing sources of truth for the same concept (Pitfall 13) | Never |
| Compute provenance badges with a live per-row correlation query instead of a batched query | Simpler component code, ships faster | N+1 query pattern on every list page; compounds once correlation fan-out is real (Pitfall 16) | Prototype/spike only, never past this phase's own merge |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|------------------|-------------------|
| Six vulnerability-scanner connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) | Assuming a schema migration alone "adds enrichment support" without touching each connector's own parsing code | Treat the schema change and all six connectors' ingestion rewrites as one atomic deliverable; verify per-connector with a fixture-based conformance test (Pitfall 9) |
| `VulnerabilityCorrelation` / `SOURCE_COLUMN_MAP` | Extending source filtering/badges on top of the existing table without noticing it's already hardcoded to 4 of 6 `VulnSource` values | Fix or replace the hardcoded per-source-column schema before building provenance features on top of it (Pitfall 11) |
| `ticketing/rule_engine.py` automation rules + `saved_filters.py` | Treating these as application code that "just reads the new score" once the formula changes | Treat them as tenant data with an implicit dependency on the old score's meaning; ship a pre/post diff report and require explicit re-tuning, not silent reinterpretation (Pitfall 1) |
| `notifications/alerts.py::_check_risk_score_changes` | Leaving the ≥20-point delta-based risk-spike alert unguarded across the cutover boundary | Suppress or version-boundary-gate delta alerts for any comparison that spans old-model-to-new-model days (Pitfall 5) |
| `connectors/scheduler.py`'s single in-process `_scheduler_loop()` | Dispatching or awaiting the historical recompute from inside the scheduler's own tick | Run the one-time migration as a standalone, chunked, throttled admin script/CLI invocation outside the scheduler's tick cycle (Pitfall 7) |
| `Asset.tags` (existing free-text operational labels) | Building the new formal exposure-context fields with no relationship to already-analyst-curated `tags` values | Use existing relevant `tags` entries to seed the first auto-inference pass; never let auto-inference write back into `tags` (Pitfall 13) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Per-asset Python-loop `UPDATE` in `compute_risk_scores()` reused unchanged for a heavier, more-joined formula | Recompute wall-clock time grows linearly (or worse) with asset count × new join cost; DB connection held per-row | Convert to a single bulk `UPDATE ... FROM (subquery)` statement before adding new joins | Noticeable at a few thousand assets; VM-pegging at the full one-time-migration scale across all tenants (Pitfall 7) |
| One-time recompute run as one unbroken synchronous stretch inside the shared asyncio event loop | Scheduler ticks (SLA breach detection, ticket sync, AI batch dispatch) stall or delay for the migration's duration | Chunk the migration with explicit yield points; run it outside `_scheduler_loop()`'s own tick, ideally as a standalone script | Any tenant fleet large enough that the recompute takes more than a few seconds — directly user-visible on a single VM |
| Live per-row correlation/provenance lookup on list-page render | Vulnerabilities/Assets/CSPM list pages show a query-count spike proportional to rows rendered, not to page count | Batch provenance/correlation data into the same query (or one follow-up query) as the page's finding IDs | Noticeable once a page renders 50+ correlated findings; compounds further with Pitfall 11's schema fix if it moves to a join table |
| `seen_by_sources.contains([s])` JSONB-array filtering on Assets without a GIN index (verify whether one exists; `tags` has a documented GIN index from migration 025, `seen_by_sources` was not confirmed to) | Asset source-filter queries scan the whole table rather than using an index as the fleet grows | Confirm/add a GIN index on `seen_by_sources` before shipping it as a first-class scanner-source filter facet | Query-plan degradation as a tenant's asset count grows into the thousands |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| One-time recompute/migration script written as new cross-tenant bulk SQL instead of reusing the existing per-tenant-scoped function | Tenant A's data (scores, correlation, exposure inference) leaks into or influences Tenant B's computed values | Iterate the existing tenant-scoped `compute_risk_scores`-style function per tenant; add a two-tenant isolation regression test specifically for the migration path (Pitfall 6) |
| No audit event for exposure-context admin overrides or risk-model-version cutover actions | New mutating actions (criticality override, model-version flip) go unlogged, breaking the milestone's own stated audit-event requirement for new mutating actions | Register audit events for criticality/data-sensitivity overrides and for the migration's per-tenant cutover action, matching the existing audit-log discipline used elsewhere in the codebase |
| Treating a missing native signal (e.g., Defender's hardcoded `cisa_kev=False`) as a verified negative in security-relevant scoring/badging | Under-scores or mis-badges genuinely KEV-listed CVEs on Defender-only-covered assets, creating a false sense of safety in a security product | Fix the hardcode; model signal-absence explicitly rather than as an implicit false (Pitfall 10) |
| Provenance badges implying independent multi-source confirmation for single-source findings | Analyst over-trusts a single scanner's finding as cross-validated, potentially deprioritizing genuine triage scrutiny | Explicit, visually distinct single-source vs. confirmed-multi-source badge states (Pitfall 16) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Trend chart shows an unexplained cliff/jump on the cutover date (Pitfall 5) | Analyst loses trust in the trend chart, may misread the jump as a real security-posture change | Annotate the model-version boundary visibly; consider splitting the chart into clearly-labeled before/after series |
| Risk-spike notification storm on cutover day (Pitfall 5) | Analysts get flooded with false "risk change" alerts for the entire fleet simultaneously, drowning any genuine signal | Suppress/gate delta-based alerts across a detected model-version boundary |
| Two competing "is this internet-facing" signals visible for the same asset with no indicated precedence (Pitfall 13) | Analyst can't tell which value to trust, erodes confidence in both the manual tagging system and the new exposure-context feature | One authoritative field with an explicit, visible override/auto-inferred discriminator and reasoning tooltip |
| CSPM's "AND" toggle behaves differently from Vulnerabilities' "AND" toggle with no UI explanation (Pitfall 15) | Analyst applies the same mental model across screens and gets surprised/wrong results on CSPM | Explicit copy distinguishing what AND means per screen if the underlying semantics genuinely differ, rather than presenting a uniform-looking control with non-uniform behavior |
| Provenance badge visually indistinguishable between single-source and multi-source-confirmed (Pitfall 16) | Analyst over-trusts unconfirmed findings, undermining the entire value of a "source-aware" product | Distinct visual/copy treatment for confirmed (2+/HIGH/MEDIUM confidence) vs. single-source-reported |

## "Looks Done But Isn't" Checklist

- [ ] **Risk model rebuild ships:** Often missing a `risk_model_version` column and a pre/post diff report for tenant-authored `min_risk_score` thresholds in automation rules/saved filters — verify by seeding a tenant with an existing automation rule, running the cutover, and confirming the rule's *effective match set* was reviewed/reported, not silently reinterpreted.
- [ ] **Historical recompute ships:** Often missing chunking/throttling and a two-tenant isolation test — verify by killing the migration mid-run and re-running it (should resume cleanly, not double-mutate or corrupt state), and by seeding two tenants with overlapping CVE IDs and confirming neither influenced the other's score.
- [ ] **Connector enrichment ships:** Often missing the actual per-connector ingestion rewrite (schema exists, six parsers still don't populate it) — verify with a fixture-based conformance test per connector, and confirm the Defender `cisa_kev=False` hardcode was actually fixed, not just documented.
- [ ] **Correlation/provenance fix ships:** Often missing coverage for all six `VulnSource` values, not just the original four — verify `sources_count == len(sources)` holds for a seeded Qualys+Rapid7-only correlation.
- [ ] **Exposure context ships:** Often missing an override-precedence test and a criticality-proportion sanity check — verify an override survives a subsequent auto-inference re-run untouched, and that the inferred-critical proportion on seed data isn't implausibly high.
- [ ] **Source filtering ships:** Often missing the AND-toggle's actual de-duplication behavior for Vulnerabilities (returns 2 rows instead of 1 correlated finding) — verify by seeding a genuinely 2-source-correlated CVE-on-asset and confirming the AND-filtered count is 1, not 2.
- [ ] **Provenance badges ship:** Often missing a batched query (N+1 live correlation lookup per row) and a visually distinct single-source state — verify via a query-count check on a list page render and a design review of the unconfirmed-single-source visual treatment.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|-----------------|
| New score formula found to be miscalibrated after full cutover (Pitfall 4) | HIGH | Requires the pre-migration backup column (Pitfall 3) to exist; restore old scores from backup, re-flag consumers to read the restored values, fix the formula, re-run the shadow/diff-report process before attempting cutover again — without a backup column, this becomes a from-scratch re-derivation that may not even be possible if source enrichment data has since changed |
| Tenant-bleed discovered in the recompute job (Pitfall 6) | HIGH | Halt the migration immediately; audit which tenants' scores were influenced by cross-tenant data; re-run the migration per-tenant from a clean state for affected tenants only; add the missing isolation regression test before resuming for remaining tenants |
| Risk-spike alert storm fires on cutover day (Pitfall 5) | LOW-MEDIUM | Suppress/clear the false notifications for the cutover window retroactively; add the version-boundary guard; communicate to affected tenants that the spike was a scoring-model artifact, not a real change |
| Automation rules misfire en masse after cutover (Pitfall 1) | MEDIUM | Pause affected tenants' automation rules; run the diff report retroactively; work with affected tenants to re-tune thresholds; consider a temporary rollback of just the rule-evaluation path to the old score while the SLA/sort/trend paths stay on the new one, if the version-tracking design supports partial rollback |
| Provenance badge overclaims confirmation, later discovered in a customer escalation (Pitfall 16) | LOW | Ship the corrected visual/copy distinction; audit any tickets/decisions made based on the miscommunicated confidence level is likely out of scope to reconstruct, but the fix itself is cheap once identified |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| 1. Tenant-authored automation rules/saved filters reinterpreted | Risk Model Rebuild phase | Pre/post diff report run against every tenant's actual `min_risk_score` rules and saved filters before cutover |
| 2. Duplicated hardcoded severity buckets | Risk Model Rebuild phase | Cross-endpoint regression test: dashboard tiles, stats endpoint, and export bucket counts agree for the same seeded tenant |
| 3. No score-model version tag | Risk Model Rebuild phase (prerequisite to Historical Recompute) | Schema review confirms `risk_model_version`/backup column exists before any recompute code is written |
| 4. No shadow/comparison period | Risk Model Rebuild phase (mechanism) + Historical Recompute phase (review) | A per-tenant diff report artifact reviewed by a human before consumers flip to the new score |
| 5. Trend/alert discontinuity at cutover | Risk Model Rebuild phase (version boundary) + Historical Recompute phase (guard implementation) | `_check_risk_score_changes` and the trend chart both demonstrably handle a seeded cutover-boundary date without false signals |
| 6. Cross-tenant recompute bleed | Historical Recompute / Migration phase | Live two-tenant isolation regression test against real (not mocked) overlapping data |
| 7. Recompute pegs the single VM | Historical Recompute / Migration phase | Load test against a realistic asset/finding fixture, measuring both migration runtime and concurrent live-request latency during the run |
| 8. Partial-failure mixed old/new scores | Historical Recompute / Migration phase | "Kill mid-run and re-run" test demonstrates clean resumption with no double-mutation |
| 9. Ad hoc per-connector signal flattening | Connector Enrichment phase | Fixture-based conformance test per connector confirming native signals are actually parsed from the raw payload, not left null |
| 10. Missing signal misread as negative | Risk Model Rebuild phase (formula) + Connector Enrichment phase (capability documentation) | Test asserting a signal-poor-source CRITICAL finding scores comparably to a signal-rich-source CRITICAL finding |
| 11. JSONB drift + hardcoded correlation columns | Connector Enrichment phase (prerequisite before Provenance Badges) | `sources_count == len(sources)` regression test; live check that Qualys/Rapid7-only correlations surface correctly |
| 12. EPSS/KEV staleness | Connector Enrichment phase | Explicit documented decision (refresh job vs. staleness bound) recorded in Key Decisions, not left ambiguous |
| 13. Exposure-context override precedence / tags conflict | Exposure Context phase | Test: set an override, re-run auto-inference, assert the override is untouched; confirm existing `tags` values seed (not get overwritten by) the first inference pass |
| 14. Criticality inflation | Exposure Context phase (calibration) + Risk Model Rebuild verification (metric tracking) | Proportion sanity check on inferred-critical assets against seed/production-like data; SLA-breach/automation-volume tracked pre/post rollout |
| 15. Source OR/AND semantics differ per entity + double-counting | Source Filtering phase | One multi-source-seeded regression test per entity (Vulnerabilities, Assets, CSPM, Tickets) asserting both OR and AND counts match analyst expectation |
| 16. Provenance badges overclaim confirmation + N+1 performance | Provenance Badges phase | Design review confirming distinct single-source vs. confirmed visual states; load test confirming batched (not per-row) provenance queries on a realistically-correlated fixture |

## Sources

- Direct code inspection (HIGH confidence, primary evidence for every GetVul-specific claim above):
  - `backend/app/assets/risk_score.py` — current formula, per-row `UPDATE`-in-loop pattern, severity weights/multipliers
  - `backend/app/vulnerabilities/correlation_service.py` — `SOURCE_COLUMN_MAP` hardcoded to 4 of 6 `VulnSource` values, confidence-tier logic, `get_correlation_for_vuln()` reconstruction gap
  - `backend/app/connectors/scheduler.py` — single in-process asyncio scheduler loop, inline `await`ed SLA/ticket-sync/snapshot work, 60-second tick
  - `backend/app/connectors/{crowdstrike,defender,nessus,rapid7,wiz,qualys}.py` — per-connector native-signal-to-boolean flattening, Defender's hardcoded `cisa_kev=False`, absence of `epss_score` population anywhere
  - `backend/app/vulnerabilities/models.py`, `backend/app/assets/models.py`, `backend/app/cspm/models.py` — `VulnSource` enum (6 values), `Asset.tags`/`seen_by_sources` shape, `Misconfiguration`'s single-source-column-no-correlation-table shape
  - `backend/app/export.py`, `backend/app/assets/router.py`, `backend/app/vulnerabilities/dashboard.py` — duplicated hardcoded risk-tier boundaries across three files
  - `backend/app/notifications/alerts.py::_check_risk_score_changes` — cross-day risk-score delta alerting with no version-boundary awareness
  - `backend/app/ticketing/rule_engine.py`, `backend/app/vulnerabilities/saved_filters.py` — tenant-authored `min_risk_score` thresholds as data, not code
  - `backend/app/ai/cache.py`, `backend/app/ai/explain.py`, `backend/app/vulnerabilities/service.py::get_top_findings_for_ai_batch` — v3.0 AI subsystem's existing dependency on `Asset.risk_score` as a sort/grounding input
  - `.planning/PROJECT.md` — v4.0 milestone scope/constraints, existing tenant-isolation/audit/single-VM constraints, prior-milestone quality-gate discipline
- General domain framing (MEDIUM confidence, standard practice, not tied to a single external doc): score-migration shadow-period/dual-write patterns, EPSS's documented daily-refresh cadence and CISA KEV's rolling-update nature are well-established properties of those public feeds, not GetVul-specific claims.

---
*Pitfalls research for: replacing an authoritative deterministic risk score, connector-native-signal enrichment, auto-inferred asset exposure context, and scanner-source-aware filtering/provenance in an existing multi-tenant vulnerability-triage platform (GetVul v4.0)*
*Researched: 2026-08-04*
