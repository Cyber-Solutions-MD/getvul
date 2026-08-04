---
phase: 28-eval-cost-observability-gate
audit: 2026-08-04
status: passed
threats_open: 0
threats_closed: 12
threats_total: 12
asvs_level: 2
auditor: Claude (gsd-secure-phase)
---

# Phase 28 — Security Audit: Eval + Cost + Observability Gate

**Verdict:** SECURED — 12/12 declared threats CLOSED (10 `mitigate` verified in source, 2 `accept` documented below).
**Method:** Every `mitigate` disposition was confirmed by reading the cited source, not by trusting SUMMARY/VERIFICATION prose. The prior functional verification (`28-VERIFICATION.md`, 13/14) was cross-referenced but each security-critical claim (tenant scoping, guard-before-dispatch, breaker parity, RBAC enforcement, CI fork-guard) was independently re-confirmed at the source line level.

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence (independently confirmed) |
|-----------|----------|-------------|--------|-------------------------------------|
| T-28-01 | Tampering / EoP — prompt injection across 5 AI capabilities | mitigate | CLOSED | `backend/tests/test_ai_injection_redteam.py` — 17 payloads × 5 real `build_explain_*_prompt` builders (85 parametrized cases). Assertions are real: payload **absent** from system prompt (`:220`), present **only as JSON data** inside `<scanner_data>` and round-trips via `json.loads` to the exact payload (`:237`), and a tag-boundary breakout count-equality check (`:246`) proving an embedded `</scanner_data>` never becomes a structural close tag. |
| T-28-02 | DoS (financial) — no route/batch path reaches billed dispatch over budget | mitigate | CLOSED | Guard-before-dispatch confirmed in source: `explain.py:308` `check_tenant_budget()` returns early (`:323`) **before** client construction (`:339`); `batch.py:261` `would_exceed_budget_for_batch()` gates **before** the billed `client.messages.batches.create()` (`:278`). Coverage suite `test_ai_budget_coverage.py`: Test A over-budget `call_count == 0` (`:198`) with a falsifiable under-budget control `>= 1` (`:229`) targeting the module-local `app.ai.explain.AsyncAnthropic` (not the tautological SDK-level patch); Test B batch `batches_created == 0` while `count_tokens_calls >= 1` (`:300`), proving the construct-then-count-then-gate asymmetry is intentional and the billed dispatch stays unreachable. |
| T-28-03 | Information Disclosure — cross-tenant leakage (IDOR) on usage endpoint | mitigate | CLOSED | `backend/app/api/v1/ai/usage.py` — **every** query is scoped by `AuditLog.tenant_id == user.tenant_id`: the 6-row capability breakdown (`:78`) and the degraded-calls count (`:118`). `spent`/`model`/`configured` all resolve via `user.tenant_id` (`:66-67,:71`). No user-supplied tenant identifier is accepted anywhere; tenant comes only from the authenticated `CurrentUser`. No cross-tenant read path exists. |
| T-28-04 | Elevation of Privilege — admin-only RBAC on usage + settings surfaces | mitigate | CLOSED | `usage.py:64` gates the route with `Depends(require_admin)`. `app/auth/rbac.py:52` `require_admin = RequireRole("ADMIN")`; `:41-44` raises `HTTP_403_FORBIDDEN` when the caller's role level is below ADMIN — so viewer/analyst → 403, admin/owner → 200. Frontend `ADMIN_ONLY` membership (`settings-sidebar-shell.tsx:59`) is UX-only hide; the authoritative gate is the backend dependency (a hand-crafted `?category=ai` still hits `require_admin` → 403). |
| T-28-05 | Information Disclosure — golden fixtures leaking real/PII data | mitigate | CLOSED | All 10 `backend/tests/evals/goldens/**/*.json` carry `capture_method: "hand_authored"` (synthetic by construction — never captured-then-redacted real data). Secret-pattern scan (`sk-ant`, `api_key`, `password`, `PRIVATE KEY`, `bearer`) and owner-PII field scan (`owner`/`assignee`/`email`/`full_name`/`phone`/`manager`) both return **zero** matches. (The hand-authored vs. real-model provenance question is a functional-quality item tracked in `28-VERIFICATION.md`; from a data-disclosure standpoint hand-authoring strictly *reduces* this threat.) |
| T-28-06 | Information Disclosure — CI live-eval secret exposed to fork PRs | mitigate | CLOSED | `.github/workflows/ci.yml` `ai-live-eval-optin`: `continue-on-error: true` (`:258`), `HAS_DEV_KEY: ${{ secrets.DEV_ANTHROPIC_API_KEY != '' }}` env-indirection (`:260`), job-level `if: github.event.repository.fork == false` (`:261`), and `DEV_ANTHROPIC_API_KEY` referenced **only** inside steps gated `if: env.HAS_DEV_KEY == 'true'` (`:282`, `:293`). For a fork PR on the `pull_request` trigger GitHub natively withholds repo secrets → `HAS_DEV_KEY` is `'false'` → all key steps skip via the "Skip if no dev key" guard (`:265-266`). Secret is never logged and never reaches a fork runner. **Fail-closed: no key → skip.** See Observation 1 for a semantic nuance on the `repository.fork` guard (does not change the CLOSED verdict). |
| T-28-07 | Tampering — an eval could assert a weaker contract than production | mitigate | CLOSED | `backend/tests/evals/metrics.py` imports (`:37-45`) and directly calls the **production** gates from `app.ai.schemas`: `ExplainResponseBase.model_validate_json()` (`:126`, `:158`) and `recheck_business_rules(...)` (`:159`). No re-implemented/weaker validator; no `evaluation_model`/`GEval`/`FaithfulnessMetric`/`api_key` references (structural metrics only). |
| T-28-08 | Information Disclosure — deepeval telemetry egress in CI | mitigate | CLOSED | `DEEPEVAL_TELEMETRY_OPT_OUT: "1"` set on the blocking eval invocation (`ci.yml:182`) and the opt-in tier (`:283`). No Confident API key configured → no eval data leaves the runner. |
| T-28-09 | Tampering / mis-observability — divergent `breaker_tripped` hides overspend | mitigate | CLOSED | `usage.py:70` `breaker_tripped = monthly_cap_usd is not None and spent >= monthly_cap_usd` is the exact inverse of `budget.py:80` `return spent < monthly_cap_usd` — identical comparison, single source of truth. Frontend `ai-usage-pane.tsx` consumes `data.breaker_tripped` directly (`:119`, `:234`) with **no** client-side spent-vs-cap re-derivation (confirmed: no `>=`/budget comparison in the component). |
| T-28-10 | Information Disclosure — breaker/budget display fidelity | accept | CLOSED (accepted) | See Accepted Risks. The pane renders only what the tenant-scoped, admin-gated endpoint returns and never independently accesses tenant data or recomputes `breaker_tripped`. |
| T-28-11 | Tampering (gate evasion) — CI checks not genuinely merge-blocking | mitigate | CLOSED | `.github/branch-protection.json` `required_status_checks.checks[]` contains **both** blocking job names byte-for-byte: `"AI Golden-Set Evals (DeepEval)"` and `"AI Prompt-Injection Red-Team (static)"`. Neither blocking job carries `continue-on-error`. The opt-in job `"AI Live Eval + Red-Team (opt-in, non-blocking)"` is **absent** from the required list, matching its `continue-on-error: true` non-blocking design. |
| T-28-12 | DoS (CI cost) — keyless blocking jobs | accept | CLOSED (accepted) | See Accepted Risks. Both blocking jobs are keyless, deterministic, no external egress; `ai-evals` needs no DB/Redis (static JSON), `ai-redteam-injection` reuses the existing backend service block. |

## Security-Critical Independent Confirmations

The six concerns called out in the audit request were each re-derived from source (not accepted from documentation):

1. **Tenant isolation / IDOR** (`usage.py`) — CONFIRMED. Every aggregation and the degraded-count query filter on `AuditLog.tenant_id == user.tenant_id`; tenant is drawn only from the authenticated principal, never from request input.
2. **RBAC admin-only** — CONFIRMED. `Depends(require_admin)` → `RequireRole("ADMIN")` raises 403 below ADMIN; frontend hide is UX-only, backend is authoritative.
3. **Fail-closed budget breaker, no bypass** — CONFIRMED. Guard precedes billed dispatch on both the 5 explain routes (`explain.py:308 < :339`) and the batch path (`batch.py:261 < :278`); comparison is fail-closed (`spent < monthly_cap_usd`); a non-tautological coverage suite (with a falsifiable under-budget control) proves it.
4. **Prompt-injection resistance** — CONFIRMED. 85 real-builder cases assert data-only isolation inside `<scanner_data>`, including delimiter-breakout resistance.
5. **CI secret handling** — CONFIRMED. Secret is key-gated via `HAS_DEV_KEY` indirection and never reaches fork-PR runners (GitHub native withholding + skip guard); opt-in tier is non-blocking.
6. **No committed secrets/keys** — CONFIRMED. Goldens are synthetic with zero secret/PII matches; `capture_ai_goldens.py` reads the key exclusively from `os.environ.get("GETVUL_DEV_ANTHROPIC_KEY")` (`:398`), no hardcoded key.

## Accepted Risks Log

- **T-28-10 — breaker/budget display fidelity (Information Disclosure, ACCEPTED).** The admin usage pane has no independent client-side data access: it renders only the tenant-scoped, `require_admin`-gated `/api/v1/ai/usage` response and consumes the server-derived `breaker_tripped` verbatim (never recomputing spent-vs-cap). Display fidelity is therefore guaranteed by the single backend source of truth (T-28-09). Residual risk is limited to server-side correctness, which is covered by T-28-03/T-28-04/T-28-09. Accepted per `28-04-PLAN.md` threat register.
- **T-28-12 — CI cost of keyless blocking jobs (DoS, ACCEPTED).** `ai-evals` (static JSON, no DB/Redis) and `ai-redteam-injection` (reuses the existing backend service block) are bounded, deterministic, and perform no external network egress. Marginal CI-minute cost is accepted as the price of genuine merge-blocking enforcement. Accepted per `28-05-PLAN.md` threat register.

## Unregistered Flags

None. No SUMMARY file (`28-0{1..5}-SUMMARY.md`) declares a `## Threat Flags` / new-attack-surface section, and no implementation surface outside the 12-entry STRIDE register (T-28-01…T-28-12) was found. All shipped attack surface maps to a registered threat.

## Observations (informational — do not change the verdict)

1. **`github.event.repository.fork == false` semantics (T-28-06).** For a fork PR on the `pull_request` trigger, the workflow runs in the *base* repository's context, where `github.event.repository.fork` is `false` — so this specific guard does **not** by itself block a fork-originated PR from entering the job. The security outcome (no secret exposure to forks) nonetheless holds robustly because GitHub does not expose repository secrets to `pull_request` runs originating from forks, which drives `HAS_DEV_KEY` to `'false'` and skips every key-using step. The mitigation is effectively delivered by the `HAS_DEV_KEY` indirection + native fork-PR secret withholding; the `repository.fork == false` line is a defense-in-depth belt that is partly redundant and whose in-code comment ("never runs on fork PRs") slightly overstates its own contribution. No key leakage path exists either way — recorded for accuracy only.
2. **Pre-existing out-of-scope CI gap (not a Phase 28 threat).** `28-VERIFICATION.md` and `deferred-items.md` note the untouched `Backend` CI job lacks an `ENCRYPTION_KEY` env var for 5 Phase 24-27 test files. This predates Phase 28, is outside this phase's modified files, and is not part of any Phase 28 threat disposition. Flagged for visibility, not counted against this audit.

## Conclusion

All twelve declared threat dispositions are satisfied in the implemented code: ten `mitigate` threats have their mitigations present at the exact source locations claimed, and two `accept` threats are documented in the accepted-risks log above. No mitigation was found absent. **Status: passed (0 open).**

The functional-quality caveat carried by `28-VERIFICATION.md` (hand-authored vs. real-model golden fixtures) is orthogonal to this security audit — it neither introduces nor leaves open any threat in the register; from a data-disclosure standpoint the hand-authored fixtures strictly reduce T-28-05 exposure.

## Security Audit 2026-08-04

| Metric | Count |
|--------|-------|
| Threats found | 12 |
| Closed | 12 |
| Open | 0 |

Register origin: authored at plan time (all 5 PLAN files carry a `<threat_model>` block). SUMMARY threat-flag scan: no `## Threat Flags` section in any of `28-0{1..5}-SUMMARY.md` — no unregistered attack surface. Verdict re-confirmed: **passed (0 open)**.

---

*Audited: 2026-08-04 · Auditor: Claude (gsd-secure-phase) · Implementation files unmodified (read-only).*
