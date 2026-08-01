# Phase 28: Eval + Cost + Observability Gate - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

The v3.0 milestone-closing quality gate. Four deliverables, seeded from real Phase 24–27 outputs now that every AI capability exists:
- **AIE-01:** a DeepEval pytest-native eval harness in CI, asserting schema/grounding/citation (never brittle prose snapshots), against golden sets from real outputs.
- **AIE-02:** a promptfoo red-team job (prompt-injection resistance over adversarial scanner text) as its own CI check, alongside semgrep/ZAP.
- **AIE-03:** a hardened **fail-closed** per-tenant cost breaker that halts AI calls when the budget is exceeded and degrades to deterministic-score-only.
- **AIE-04:** an admin UI to view AI usage + cost and manage AI settings (key/model/budget).

**The central constraint:** BYOK is a hard privacy guarantee — there is **no GetVul-owned/shared/fallback Anthropic key, including in CI**. So the CI-blocking gates must run WITHOUT a live model call. This phase mostly HARDENS + OBSERVES existing scaffold (the Phase 24 fail-closed budget guard D-06/D-07/D-08, audit rows D-27, the injection-as-data prompt contract AI-02, the no-rank/no-PII/cite-or-refuse schema contracts) — it builds essentially no new AI *call*.
</domain>

<decisions>
## Implementation Decisions

### Keyless-CI eval + red-team execution (AIE-01/AIE-02) — the central decision
- **D-01:** **Two-tier execution.** The **CI-BLOCKING** gates are DETERMINISTIC, no-model-call: (a) DeepEval (pytest-native) asserts **structural** properties over captured golden fixtures — schema validity, grounding-traceability (every citation's `source_field` maps to a real grounding field), citation structure, the no-rank invariant, no owner-PII, and cite-or-refuse honored; (b) the promptfoo red-team asserts the **prompt-BUILDER** isolates adversarial scanner text as data (the injection-as-data contract) via static/recorded prompt inspection — the adversarial payload appears only inside the `<scanner_data>` block, never as instructions, across every AI capability's system prompt. The **LLM-judge / live-model** evals (faithfulness metric, live promptfoo attacks) run ONLY as a **separate, opt-in, key-gated job that never blocks CI** (runs when a developer supplies their own key). This honors the no-GetVul-key stance while keeping the gates real and runnable. — **Reversibility:** costly — the CI gate contract + harness shape is what "shipping without evals" (Pitfall #8) is enforced by.
- **D-06:** Eval assertions are **structural/deterministic, never exact-prose snapshots and never an LLM-judge in the blocking path** (SC1 explicit). The LLM-judge faithfulness metric is strictly the opt-in key-gated tier. This matches the codebase's "the sweep, not the file list, is the arbiter" discipline.

### Golden-set sourcing (AIE-01)
- **D-02:** **Curated captured REAL outputs, committed as fixtures.** A small, curated set of real Phase 24–27 outputs (explain / remediation-guidance / prioritization / ticket-draft) is captured ONCE from a dev key, **redacted to a synthetic tenant** (no real customer data committed), and checked into the repo as JSON fixtures the deterministic CI evals assert against. Reproducible, keyless-CI-friendly, genuinely "seeded from real observed outputs" (SC1). No live regeneration in CI. — **Reversibility:** reversible (fixtures can be re-captured).
- **D-07:** Fixture capture is a **one-time, documented dev-key operation** (a script/runbook), NOT automated in CI. Redaction to a synthetic tenant is mandatory before commit.

### Cost circuit-breaker hardening (AIE-03)
- **D-04:** Build ON the existing `check_tenant_budget()` fail-closed guard (D-06) — do NOT replace it with a token-bucket/rate-limiter (that's scope creep for the closing gate). ADD: (1) a **persistent per-tenant breaker** that, once tripped (budget exceeded), degrades **EVERY** AI surface (vuln / host / remediation / prioritization / ticket-draft / batch) to **deterministic-score-only** until the budget resets or the admin raises it; (2) a **coverage test** proving **no AI call path bypasses** the guard (the sweep-is-arbiter discipline), enforced as a CI gate. This is the milestone's cost release-gate. — **Reversibility:** costly — the breaker state + global-degrade contract.
- **D-09:** The degraded mode is a **single tenant-scoped state** the frontend reads (reusing the D-25/budget-exceeded state vocabulary) — a unified "AI paused — budget exceeded" degraded experience across surfaces, not per-surface duplicated cards. Whether the breaker state is a new persisted column or derived from month-to-date-spend-vs-cap is a plan-time detail (lean: derived, to avoid a stateful sync bug).

### Admin usage/cost + settings UI (AIE-04)
- **D-05:** A **new dedicated "AI" settings pane** (admin-only, RBAC) that shows **month-to-date cost vs budget + a per-capability usage breakdown + the breaker status** (all read from the EXISTING `ai.*` audit rows, D-27 — no new telemetry pipeline), AND **consolidates key/model/budget management** there (surfacing/linking the Phase 24 connector config so AI settings have one admin home). Follows the existing settings-pane pattern (like `audit-log-pane.tsx`). — **Reversibility:** costly — a new admin surface.
- **D-08:** The usage/cost view **aggregates the existing audit rows** (month-to-date cost, per-capability, per-model, per-status) — it introduces NO new metrics/telemetry backend beyond querying `AuditLog` for `ai.*` actions.

### Claude's Discretion
- Exact golden-fixture count + which capabilities/edge-cases to capture (D-02) — researcher recommends.
- promptfoo proper vs a lighter static-assertion harness for the CI-blocking red-team tier (D-01/D-03) — researcher pins the tool that runs keyless.
- Breaker state: derived vs persisted column (D-09) — plan-time.
- Exact usage-view metrics + layout (D-05) — a UI-SPEC decision.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 28: Eval + Cost + Observability Gate" — goal, 4 SCs, Pitfalls #5/#6/#8.
- `.planning/REQUIREMENTS.md` — AIE-01..04 (lines ~48–53, traceability ~96–99) + the BYOK privacy guarantee (line 8, constrains AIE-03/04).

### Inherited scaffold this phase hardens/observes (MUST read)
- `backend/app/ai/budget.py` — `check_tenant_budget()` / `would_exceed_budget_for_batch()` fail-closed guard (AIE-03 base, D-06/D-07).
- `backend/app/ai/audit.py` + the `AuditLog` model — `ai.*` rows with model/tokens/cost/status/tenant (AIE-04 data source, D-27).
- `backend/app/ai/prompt_builder.py` — the `<scanner_data>` injection-as-data system prompts the red-team (AIE-02) inspects; the response schemas (no-rank, citations) the evals (AIE-01) assert on.
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-CONTEXT.md` — D-06/07/08 (budget+alert), D-27 (audit), D-25 (degraded-state vocabulary), and any `*-AI-SPEC.md` (the milestone eval strategy this phase implements).
- `.planning/phases/26-prioritization-narrative/26-*` — the 50%-batch-cost booking the breaker's month-to-date SUM depends on.

### CI + settings surfaces
- `.github/workflows/ci.yml` — where the DeepEval + red-team jobs land, alongside semgrep/ZAP (AIE-01/02).
- `frontend/src/components/settings/*-pane.tsx` (esp. `audit-log-pane.tsx`) — the settings-pane pattern the new AI pane follows (AIE-04); `frontend/src/components/connectors/wizard/` (Phase 24) — the key/model/budget config to consolidate/surface.
- `.claude/skills/sketch-findings-getvul/` — MANDATORY before UI.

### New tooling (research territory)
- **DeepEval** (pytest-native eval harness) + **promptfoo** (red-team) — new deps; the researcher pins how each runs in a keyless CI (deterministic/static tier) vs a key-gated tier, using current docs.

### Milestone constraint
- The AI BYOK privacy stance (memory `getvul-ai-byok-privacy-stance`): no GetVul-owned/shared/fallback key, ever — including CI. This is why D-01's blocking gates are keyless.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `check_tenant_budget()` fail-closed guard — AIE-03 extends it (global degrade + coverage test), does not replace it.
- `audit_log_ai_call()` + `AuditLog` `ai.*` rows — the AIE-04 usage/cost data, already carrying model/tokens/cost/status/tenant.
- The settings-pane pattern (`audit-log-pane.tsx` et al.) — the new AI pane mirrors it; RBAC/admin-gating precedent.
- The injection-as-data `<scanner_data>` prompt contract + the no-rank/citation response schemas — what the deterministic evals + red-team assert against.

### Established Patterns
- Fail-closed budget + degraded-state vocabulary (D-06/D-25) — the breaker's global degrade reuses it.
- "The sweep is the arbiter" — a coverage test proving no AI call bypasses the guard (D-04), mirroring the axe-sweep/eval-as-arbiter discipline.
- Existing CI jobs (semgrep/ZAP in ci.yml) — the red-team + eval jobs slot in as sibling checks.

### Integration Points
- CI: new DeepEval pytest job + red-team job in ci.yml (blocking, keyless) + an opt-in key-gated live-eval job (non-blocking).
- Frontend: new admin AI settings/usage pane reading `ai.*` audit aggregates + the breaker status + linking the connector config.
</code_context>

<specifics>
## Specific Ideas

- Keyless-CI-first: the blocking gates never call a model (BYOK = no CI key). Live LLM-judge evals are opt-in, key-gated, non-blocking.
- Seeded from real: curated real Phase 24-27 outputs, redacted to a synthetic tenant, committed as fixtures — not synthetic, not regenerated in CI.
- Fail-closed as a release gate: global degrade-to-deterministic + a no-bypass coverage test, built on the existing guard.
- One admin home for AI: usage/cost + breaker status + key/model/budget in a dedicated pane, all from existing audit rows.
- The evals assert structure (schema/grounding/citation/no-rank/no-PII/cite-or-refuse), never prose.
</specifics>

<deferred>
## Deferred Ideas

- **LLM-judge faithfulness as a CI-BLOCKING gate** — OUT (keyless CI; it's the opt-in key-gated non-blocking tier per D-01).
- **A GetVul-owned eval/CI key** — OUT (violates the no-GetVul-key privacy guarantee).
- **Token-bucket / per-minute rate-limiter breaker** — OUT (AIE-03 wants halt-when-budget-exceeded fail-closed, not a rich rate limiter).
- **AINL-01 natural-language query** — already deferred to v3.1 (not in this phase set).
- **New telemetry/metrics backend** — OUT (AIE-04 aggregates existing audit rows).

None of the above are built in Phase 28.
</deferred>

---

*Phase: 28-eval-cost-observability-gate*
*Context gathered: 2026-08-01*
