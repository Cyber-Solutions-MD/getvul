# Milestones — GetVul

## v4.0 Enriched Risk Exposure & Source-Aware Triage (Shipped: 2026-08-13)

**Phases completed:** 6 phases, 25 plans, 69 tasks

**Key accomplishments:**

- Replaced the 4-of-6-source hardcoded FK-column shape on `vulnerability_correlations` with a `sources ARRAY(String)`+GIN / `source_vuln_ids` JSONB pair generalized over the full 6-value `VulnSource` enum, proving end-to-end that a previously-silently-dropped Qualys+Rapid7 correlation now round-trips correctly through model → migration → service → API-shaping.
- Idempotent per-tenant re-correlation script (`_recorrelate_tenant`) that runtime-proves CORR-02 zero-loss recovery of the previously-silently-dropped Qualys/Rapid7 correlations, plus a 10-test suite locking CORR-03's count/name invariant, D-08 confidence bands, cross-tenant isolation, and the D-09 HTTP contract as standing regressions.
- Threaded EPSS score+percentile and catalog-authoritative CISA KEV through the single `_upsert_vulnerability` choke point for every connector, and gave Defender its full `source_signals` allowlist + explicit-null native-priority pair — proving the entire enrichment schema and write-path end-to-end on one connector before the remaining 5 connectors build on it.
- Daily 24h-gated scheduler job that fetches the real EPSS CSV + CISA KEV JSON feeds, atomic-swaps them into the global reference tables (keeping last-good data on any failure), and re-propagates the refreshed values onto every existing finding by cve_id — verified live against the real feeds (355,094 EPSS rows, 1,660 KEV rows), and hardened against a genuine concurrency race discovered during that live verification.
- CrowdStrike's ExPRT.AI rating and Nessus's VPR score now populate `native_priority_rating`/`native_priority_score` straight from already-fetched vendor payloads (zero new API calls for CrowdStrike, one defensive probe for Nessus), with both connectors' risk-relevant fields threaded into `source_signals` using missing-vs-negative semantics and a hard no-PII/no-promoted-duplicate boundary.
- Qualys's Detection Score (QDS) and Rapid7's Risk Score now populate `native_priority_score` straight from the correct-but-non-obvious source location for each vendor (the per-detection record, not the QID knowledge base; the per-asset association entry, not the vendor-neutral vulnerability definition), completing native-priority coverage for all 4 composite-signal connectors, with both connectors' risk-relevant fields threaded into `source_signals` using missing-vs-negative semantics.
- Wiz's 5 richer EPSS/exploitability sub-scores now land in `source_signals` behind a GraphQL schema-error-guarded query (native priority columns stay explicit `None` — Wiz has no vendor composite), and a new cross-6 parametrized sweep proves all 6 connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) always explicitly set `native_priority_score`/`native_priority_rating`/`source_signals`, closing out Phase 31's ENRICH-03/04/06 requirements.
- End-to-end exposure-context spine (migration → model → pure inference → AUTO-gated writer → admin override → audit → API) threaded through business_criticality as the proof case, with data_sensitivity/internet_facing wired to the same pipeline at documented placeholder defaults for Plan 02.
- Real data_sensitivity + internet_facing inference completing the exposure-context triad, plus EXPO-06's AUTO-only criticality calibration report with a per-tenant configurable 15% cap (flag+report, hard-cap deliberately unwired).
- A real tenant-scoped AssetGroup entity (model + membership + admin CRUD) with a GROUP_OVERRIDE precedence tier inserted between per-asset override permanence and auto-inference — most-recently-updated group wins on multi-group conflict, and membership add/remove re-applies precedence immediately.
- Landed the full detected-signal schema spine (NormalizedVulnerability.internet_facing, Asset.internet_facing_detected, sync passthrough, infer_exposure_context precedence) and, after directly inspecting all 6 connectors' actual raw payload/GraphQL shape, honestly documented that none of them currently exposes a distinct internet-facing signal — every connector stays FALLBACK to the v1 external_ip/tag proxy.
- Asset detail page gains an ExposureContextCard (3 fields + auto/manually-set/group:{name} source badges + admin inline override), and a new /dashboard/asset-groups page delivers full AssetGroup CRUD + membership + per-group override management — both admin-gated in the UI as defense-in-depth, backed by two small, additive backend read endpoints this plan discovered were missing.
- Per-finding risk-exposure scoring spine landed end-to-end: migration → model columns → pure `score_finding` (severity/CVSS + EPSS + KEV floor real, everything else a zeroed Plan-33-02 placeholder) → `compute_finding_risk_scores` DB-orchestration → single post-sync shadow-compute hook → persisted-column read on `GET /vulnerabilities/{id}` — zero automated consumer, grep-provable.
- `score_finding` now computes the complete 6-category, 100-point deterministic formula — per-source native-exploitability normalization (Nessus/Qualys/Rapid7 numeric scales + CrowdStrike categorical, soft-null everywhere else), the full Phase 32 exposure sub-split, and Phase 30 cross-scanner corroboration — with `compute_finding_risk_scores` now bulk-fetching real `sources_count` in a single tenant-scoped query (no N+1), and the KEV floor emitting an explicit breakdown row when it actually changes the outcome.
- `compute_finding_risk_scores` now rolls each asset's `Asset.risk_exposure_score` up to the MAX of its open findings (resetting to NULL when none remain), `Vulnerability.risk_exposure_score` carries a passive sortability index (migration 043), and the `>=80/>=50/>=20` severity-tier boundary — previously hand-synced across 3 files — collapses into one named-constant set, proven zero-behavior-change by a characterization regression.
- The DrillPanel's new "Risk exposure" section (desktop + mobile, one shared `drill-content.tsx` edit) renders the backend's shadow per-finding `risk_exposure_score` via a reused `RiskRing`, a data-driven row per `risk_exposure_breakdown` component, and a "★ KEV floor applied" chip keyed off a `kev_floor` breakdown component — all clearly labeled "Shadow score — not yet used for sorting or alerts" (RISK-05), with zero frontend re-derivation of scoring logic (RISK-06 intact).
- Durable per-tenant `RiskExposureBackfillJob` + chunked keyset-resumable bulk `UPDATE...FROM` backfill of `Vulnerability.risk_exposure_score`, dispatched via `asyncio.create_task` every scheduler tick with no in-memory gate — proven idempotent/resumable/throttled/per-tenant-isolated by a 9-test fixture suite including kill-mid-chunk and simulated-process-restart resume.
- Both genuine RISK-08 cutover consumers (`list_vulnerabilities(sort="triage")` and `get_top_findings_for_ai_batch`) now branch their primary ordering key on `Tenant.cutover_risk_exposure_scoring` via a once-per-call scalar Tenant fetch — proven byte-identical OFF (default) and correctly re-ranked by the new per-finding `risk_exposure_score` ON, with SLA and the two `min_risk_score` threshold sites left deliberately untouched.
- Read-only pre/post `min_risk_score` diff report (old `Asset.risk_score` vs new `Asset.risk_exposure_score`) plus an audited per-tenant re-tuning acknowledgment that structurally gates the admin cutover flag flip — the flip cannot succeed without both a completed historical backfill AND a fresh (hash-matching) ack, and `rule_engine.py`/`saved_filters.py` are untouched.
- Unconditional dual-write of new-model risk metrics into every DailySnapshot, fixing the pre-existing dead `asset_risk_scores` read and version-boundary-guarding `_check_risk_score_changes` so a `risk_model_version` change across a day boundary produces neither an alert storm nor a trend cliff.
- Closed both gaps 34-VERIFICATION.md found (score 3.5/4): the trend chart's primary `avg_risk` series now genuinely branches on `Tenant.cutover_risk_exposure_scoring` (mirroring the already-verified `sort="triage"`/`get_top_findings_for_ai_batch` pattern), and a new admin-only `POST /api/v1/risk-cutover/backfill/enqueue` endpoint gives RISK-07's previously test-only-invoked backfill machinery a real production trigger.
- Vulnerabilities list filter now branches on the Phase-30 correlation ARRAY (`&&` OR-default / `@>` AND-toggle) instead of the per-row `Vulnerability.source.in_()`, and every list row carries `sources`/`sources_count` via a new page-scoped, tenant-scoped `tuple_(...).in_()` batched fetch proven no-N+1 by a new `before_cursor_execute` query-count harness.
- Shared, non-overclaiming SourceBadgeGroup component (single-source = 1 neutral provider mark, 2+ sources = mark group + "N sources" corroboration-tinted label) wired into the Vulnerabilities table, plus a reconciled 6-value scanner list and an OR/AND `?source_mode` toggle in the vuln chip-bar — the first UI surface to consume Plan 01's `sources`/`sources_count` API contract.
- 1. [Rule 1/2 - Bug/Missing-critical] `false()` fallback when scanner/enrichment clamp empties the list
- CSPM's cross-tool AND filter now performs TRUE corroboration via a read-time `GROUP BY(tenant_id, rule_id, resource_id) HAVING count(DISTINCT source) >= N` (never a silent `source.in_()` OR fallback), every CSPM row carries page-scoped batched `sources`/`sources_count`, and the ticket list resolves provenance transitively through each linked vuln's `VulnerabilityCorrelation` — unioning ALL linked vulns' sources per grouped ticket-task row via `array_agg(DISTINCT ...)` (never `func.min`'s representative pick) — plus a real server-side OR-default `?source=` filter on Tickets, closing SRC-02 for all four entities.
- Replicated Plan 02's proven SourceBadgeGroup + OR/AND chip-bar toggle pattern verbatim across Assets (scanner/enrichment axis split), CSPM (true multi-tool corroboration toggle), and Tickets (a real server-filtering source axis, OR-only) — closing v4.0's SRC-01..04 across all four triage entities.

---

A historical log of shipped milestones. Full per-milestone detail lives in `.planning/milestones/`.

---

## 📋 v5.0 Close the Loop — Remediation Orchestration & Assurance — PROPOSED (not started)

**Status:** DRAFT — activate via `/gsd-new-milestone` **after v4.0 ships** (avoid two active milestones). **Proposed phases:** 36–45 (10 features).

Turns GetVul from *see & decide* into *operationalize, close, and prove*: risk-tier SLA engine + escalation, two-way ticket sync + rescan-verified auto-close, remediation campaigns, exception/risk-acceptance governance, proactive KEV/EPSS alerting + digests, coverage/blind-spot detection, risk-trend/burndown analytics, executive + compliance reporting (SOC 2 / ISO 27001 / PCI / NIST CSF), a BYOK natural-language query assistant (AINL-01, deferred from v3.1), and a public API + webhooks + SDK. Research-grounded (2026 RBVM/CTEM market); scoped to GetVul's lane (a triage/orchestration layer on existing scanners, not a scanner or patch-deployer). Consumes v4.0's deterministic risk-exposure score throughout.

**Proposal:** [milestones/v5.0-PROPOSAL.md](milestones/v5.0-PROPOSAL.md) · **Requirements stub:** [milestones/v5.0-REQUIREMENTS.md](milestones/v5.0-REQUIREMENTS.md) (32 requirements across 10 families, all Pending)

---

## v3.0 AI-Assisted Triage ("Triage Copilot") — ✅ SHIPPED 2026-08-04

**Phases:** 23–29 (7 phases, 45 plans) · **Timeline:** 2026-07-27 → 2026-08-04 (~8 days) · **Audit:** `tech_debt` (21/21 requirements satisfied, 0 broken/0 orphaned/0 missing integration seams, 11/11 flows wired) · **Closeout:** override_closeout (accepted live-verification debt — see Deferred Items in STATE.md)

Added a BYOK (bring-your-own-key, tenant-supplied Anthropic key only) LLM-assistance layer — grounded in the tenant's own correlated vuln data, guardrailed against prompt injection / PII leakage / cost blowup, and gated by evals — so a triage analyst gets help *deciding and acting*, not just *seeing*. The deterministic risk score stays authoritative; AI explains and augments it, never replaces it. The hard privacy guarantee held end-to-end: no GetVul-owned/shared/fallback key, no proxied inference, tenant-scoped cache only, features inert until the tenant configures their own key.

**Key accomplishments:**

1. **AI foundation with the privacy guarantee intact** (Phase 24) — tenant-admin BYOK key config (encrypted via the Fernet/`ConnectorConfig` pattern), a buffer-validate-replay SSE engine streaming grounded, two-tier-cited "Explain this vuln" summaries through nginx, and the full reusable guardrail scaffold (untrusted-content-as-data, schema validation, tenant-scoped cache, fail-closed cost gate, audit) — shipped together at minimum blast radius, then reused unmodified by every later phase.
2. **Grounded remediation + prioritization** (Phases 25–26) — asset-aware remediation guidance that cites the scanner's own solution text or refuses rather than inventing (cite-or-refuse + dangerous-command denylist), and a "what to fix first and why" narrative that augments — never replaces — the deterministic score, pre-generated in bulk via the Message Batches API (`asyncio.create_task`, never stalling a sync tick).
3. **Ticket auto-drafting** (Phase 27) — AI-drafted title/description/remediation/asset-context pre-fills the existing Jira/Asana create flow; a human click always creates the ticket (never auto-submitted).
4. **A real CI-enforced quality gate** (Phase 28) — DeepEval golden-set evals + a promptfoo prompt-injection red-team (17 payloads × 5 capabilities = 85 cases) as required status checks, a fail-closed per-tenant cost circuit breaker, and an admin AI usage/cost/settings pane.
5. **Ingestion reliability precursor** (Phase 23) — fixed the silently-broken Wiz + Rapid7 sync bugs, added HTTP-layer integration tests for all 6 scanners (the gap that let them ship), wired Jira ticket-create + finished GitHub ticketing, and surfaced per-connector sync health/last-error.
6. **Auth hardening** (Phase 29, backlog-promoted WR-02) — replaced the ad-hoc default-credential rejection on the forced-rotation endpoint with a real complexity + password-history + similarity/edit-distance policy, closing the Phase 06 `Admin1234!` near-variant residual.

**Verification:** all 7 phases verified `passed`; the integration checker traced 20+ cross-phase export/import chains and re-ran the AI backend suite (24 test files) + the 6-connector HTTP-layer suite (0 broken / 0 orphaned / 0 missing).

**Archive:** [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) · [milestones/v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) · [milestones/v3.0-MILESTONE-AUDIT.md](milestones/v3.0-MILESTONE-AUDIT.md)

**Tech debt carried forward (all accepted, non-blocking — see STATE.md Deferred Items + v3.0-MILESTONE-AUDIT.md):** Category A — live-Anthropic-key / live-browser verification waived on-trust at the tracer gates for Phases 24–27 (closeable via `/gsd-verify-work <N>`); Category B — Phase 28 hand-authored golden fixtures + 3 external-infra eval-gate overrides; **Category C (actionable) — the pre-existing `backend` CI job lacks `ENCRYPTION_KEY` and will fail 5 Phase 24–27 test files against a synced origin (one-line fix logged in Phase 28 deferred-items.md)**; Category D — carried Phase 23 ticketing WARNINGs (duplicate `/sync-status` route, unvalidated `TicketRuleAction.provider`); plus Nyquist VALIDATION.md doc reconciliation for phases 24–27/29 (documented-stale per project memory, real suites green). AINL-01 (natural-language query) deferred to v3.1.

---

## v2.2 Deferred UI Features — ✅ SHIPPED 2026-07-22

**Phases:** 16–22 (7 phases, 23 plans) · **Timeline:** 2026-07-15 → 2026-07-22 · **Audit:** `passed` (22/22 UX-D requirements, 9/9 integration seams, 5/5 flows)

Finished the four features deferred out of v2.0 as net-new work, each holding the phase-15 quality gate (axe WCAG 2.1 AA in **both** themes, reduced-motion, ≤250 KB First-Load JS/route) and the `sketch-findings-getvul` design contract. Phases 16–19 shipped the features; the v2.2 audit (2026-07-20) then found three verification gaps, which Phases 20–22 closed.

**Key accomplishments:**

1. **Light theme completed for real** (Phases 16, 20) — ~20 light-mode token overrides + a working `Theme: Light` toggle; added `--color-severity-high-on-soft` (#9A3412) and `--color-severity-critical-on-soft` (#991B1B), migrated all foreground severity text to the on-soft tokens, and got the blocking axe sweep GREEN across 11 routes in both themes — proven against a live prod build, not merely claimed (closing UX-D-03).
2. **Page transitions via the native View Transitions API** (Phases 17, 21) — pathname-keyed `(authed)/template.tsx` cross-fade, suppressed under `prefers-reduced-motion`, Firefox CSS fallback, 0 KB added; formally verified with a `firefox-transitions` Playwright project and a persisted perceptual human-UAT (UX-D-06).
3. **Tickets kanban board** (Phase 18) — @dnd-kit four-column board (Open / In progress / Completed / Blocked) with pointer + touch + keyboard sensors, optimistic move + rollback, kept off the route bundle via `next/dynamic({ssr:false})` (`/dashboard/tickets` at 167 kB) (UX-D-01).
4. **Add-connector wizard** (Phase 19) — guided four-step flow (provider → credentials → test → confirm) gated on a real connection test, reusing existing endpoints + sentinel-passthrough, inside the ResponsiveDialog/vaul mobile pattern (`/dashboard/connectors` at 156 kB) (UX-D-02).
5. **Test-coverage hardening** (Phase 22) — converted the two audit warnings into live, deterministic e2e assertions: the CR-01 Enter-key-drag guard + WR-02 gated-drop SR wording (which surfaced and fixed two genuine keyboard-a11y defects), and full wizard axe coverage across the Test + Confirm steps in both themes.

**Verification:** every phase shipped live-verified e2e evidence (axe both themes, kanban/wizard specs, VT specs) in its VERIFICATION.md; milestone audit passed with no gaps.

**Archive:** [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md) · [milestones/v2.2-REQUIREMENTS.md](milestones/v2.2-REQUIREMENTS.md) · [milestones/v2.2-MILESTONE-AUDIT.md](milestones/v2.2-MILESTONE-AUDIT.md)

**Tech debt carried forward (all non-blocking):** `18-HUMAN-UAT.md` bookkeeping reconciliation (items now automated in Phase 22), two cosmetic missing SUMMARY `requirements-completed` frontmatter blocks (16/17), one cosmetic dark-mode `/80`-opacity drop in `blocked-toggle.tsx`, advisory code-review warnings across P17/18/19/22 (deferrable to `/gsd-code-review-fix`), and stale Nyquist `VALIDATION.md` flags (documented-stale per project memory; real live e2e coverage shipped per phase). See [BACKLOG.md](BACKLOG.md).

---

## v2.1 Polish & Tech Debt — ✅ SHIPPED 2026-07-15

Closed the non-blocking tech debt carried in [BACKLOG.md](BACKLOG.md) from the v2.0 audit:

- **BL-01** — canonical `/dashboard/*` client-nav hrefs (removed the 308 middleware round-trips). *(PR #22)*
- **BL-02** — pointed the dead `/integrations` middleware redirect at `/dashboard/connectors`. *(PR #22)*
- **BL-03** — descriptive `useDocumentTitle` on assets-detail, cspm, connectors, users, settings. *(PR #22)*
- **BL-04** — reconciled the dark-theme contrast overrides (text-faint AA lift + accent-on-soft text tokens + "Text on -soft fills" rule) into the `sketch-findings-getvul` source of truth (sunset.css / foundation.md / visual-language.md).
- **BL-05** — closed Nyquist validation on phases 9/10/11/14/15: reconciled every VALIDATION.md against the shipped suite, wrote the one genuinely-missing test (Phase 11 `/dev/primitives` route gate), and flipped all five to `nyquist_compliant: true`.

Deferred v2.0 features (Tickets kanban board UX-D-01, full connector wizard UX-D-02, light-theme polish UX-D-03, page transitions UX-D-06) were promoted into **v2.2** (above, shipped 2026-07-22). The Safari glyph human check (BL-06) remains separately scoped (needs a Mac).

---

## v2.0 UI/UX Redesign — ✅ SHIPPED 2026-06-30

**Phases:** 9–15 (7 phases, 49 plans) · **Audit:** `tech_debt` (0 blockers, 48/48 requirements wired)

Rebuilt every authenticated screen against the Wiz-inspired sunset-palette design system as vertical slices (tokens + primitives + page + state patterns + a11y + tests), replacing v1's `!important`-hack light theme and missing primitives.

**Key accomplishments:**

1. Sunset CSS-variable token system + Tailwind rewired to consume it (zero `!important`); persistent app-shell + first primitive set (Phase 9).
2. Action-first dashboard, faceted vulnerabilities with chip-bar + 420px drill panel, and the canonical state primitives (SkeletonTable / EmptyState / PartialFailureBanner / PerSourceStatusStrip / Toast / DrillPanel) consumed verbatim by all later list screens (Phases 10–11).
3. Two-column asset & ticket detail pages (risk ring, owner card, remediation timeline, watcher stack, provider gradient marks); generalized DrillPanel for vuln/ticket/asset/finding (Phases 12–13).
4. CSPM / connectors / users / settings rebuilt; settings moved to sidebar-of-categories (Phase 14).
5. Mobile + a11y + perf quality gate (Phase 15): three-tier responsive nav, vaul bottom sheets, jsx-a11y at error, Playwright route gate, bundle budget, Lighthouse — **green on the production build** (Playwright 28 passed, 15/15 routes ≤250 KB, Lighthouse /login 97/95 + /dashboard 90/95). Mobile table card-view collapse + ~18 D-09 audit-fix defects resolved.

**Verification:** Phase 15 7/7 SC; milestone audit 48/48 wired, all E2E flows working. **Pending (non-blocking):** Safari.app glyph human spot-check.

**Archive:** [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md) · [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md) · [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md)

**Tech debt carried forward:** see [BACKLOG.md](BACKLOG.md).

---

## v1.0 Production Readiness — ✅ SHIPPED (Phase 1 2026-05-09; Phases 2–8 2026-06-30 → 2026-07-14)

All 8 phases complete. Phase 1 (Multi-Replica State) moved OIDC state + the rate limiter to Redis (PROD-01). Phases 2–8 followed: CI gating (triggers on, masks removed, gate enforcing), update-path reconciliation, doc/code parity (CSP/COOP headers, VulnSource enum), encryption-key lifecycle, default-admin hardening, health/observability (split liveness/readiness, JSON logs), and the test-coverage floor (one+ test per connector + rule engine + SLA; full backend suite 271 green).

**Late hardening (2026-07-13/14):** restored the backend CI gate end-to-end — pinned ruff/mypy, fixed the async test-harness (session-scoped event loop) + rate-limit test isolation, and fixed 4+ real bugs surfaced along the way (change-password redirect loop, tenant-settings 500, rate-limiter fail-open-under-burst, Nessus + Intune connector crashes). Also patched frontend dependency vulns (13 → 2, all high resolved). Detail in `.planning/ROADMAP.md` (v1.0 section) and `milestones/v1.0-REQUIREMENTS.md`.
