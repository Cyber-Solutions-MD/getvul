# Phase 39: Exception & Risk-Acceptance Workflow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-18
**Phase:** 39-exception-risk-acceptance-workflow
**Areas discussed:** Record vs status flag, Approver & approval, Scope semantics, FP vs accept-risk + expiry, Risk-score exclusion, Expiry input & cap, Overlap precedence, Expiring-soon visibility

---

## Record vs status flag — exclusion source of truth

| Option | Description | Selected |
|--------|-------------|----------|
| Exception table | New `exceptions` table is source of truth; LEFT JOIN active exceptions; status not flipped; expiry auto-resurfaces free | ✓ |
| Status-flip + governance row | Flip status to SUPPRESSED/FALSE_POSITIVE (reuses all existing exclusion) + governance row; lazy re-flip on expiry | |
| Hybrid: status derived FROM table | Table is truth, one shared compute-on-read "effective status" helper every consumer calls | |

**User's choice:** Exception table (source of truth, compute-on-read exclusion).
**Notes:** Cleanest governance; EXC-04 auto-resurface becomes free (join stops matching once expired). Accepted cost: exclusion consumers must learn the join.

## Record vs status flag — legacy paths

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as-is, additive | New workflow additive; exclusion = (status SUPPRESSED/FALSE_POSITIVE) OR (active exception); old endpoints stay | ✓ |
| Rewire legacy → exceptions | Point old ignore/suppress endpoints at the new exception-create path | |
| New path only, defer decision | Ship standalone; defer legacy consolidation; still union both signals | |

**User's choice:** Leave as-is, additive.
**Notes:** No migration risk; rewiring shipped endpoints (which lack approver/scope) would be scope creep. Legacy consolidation noted for a future phase.

## Record vs status flag — eligibility

| Option | Description | Selected |
|--------|-------------|----------|
| Actionable only | Grant only on OPEN/IN_PROGRESS; no-op on REMEDIATED | ✓ |
| Any status | Allow granting on any finding including REMEDIATED | |

**User's choice:** Actionable only.
**Notes:** Matches how `/cve/ignore` targets `status IN (OPEN, IN_PROGRESS)`.

---

## Approver & approval — approval model

| Option | Description | Selected |
|--------|-------------|----------|
| Recorded attribution | Single-action grant with required approver field + justification/scope/expiry; audited; no state machine | ✓ |
| Two-step pending→approved | Requester creates PENDING; a different approver approves before it excludes anything | |
| Role-gated single-actor | Single action but requires admin; the acting admin is the approver | |

**User's choice:** Recorded attribution.
**Notes:** Governance from mandatory fields + audit trail. Two-step rejected as larger than EXC-01 scopes.

## Approver & approval — RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| Analyst+ | `require_analyst`, consistent with existing suppress/ignore writes | ✓ |
| Admin only | Restrict grants to admins | |
| Split: analyst requests, admin approves | Only coherent with a two-step flow | |

**User's choice:** Analyst+.
**Notes:** Exceptions are an analyst triage workflow, not admin config.

## Approver & approval — approver representation

| Option | Description | Selected |
|--------|-------------|----------|
| Tenant user reference (FK) | Approver is a selected GetVul user; audit "who" resolves to a real identity | ✓ |
| Free-text string | Free-text approver name/email; weaker, no referential integrity | |
| User ref with free-text fallback | Prefer user ref, allow free-text override | |

**User's choice:** Tenant user reference.
**Notes:** External-approver support deferred.

---

## Scope semantics — matching

| Option | Description | Selected |
|--------|-------------|----------|
| Live membership | Scope predicate covers present AND future matching findings until expiry | ✓ |
| Frozen snapshot | Freezes exact finding IDs at grant time | |

**User's choice:** Live membership.
**Notes:** Mirrors Phase 38 D-03; compute-on-read join handles it for free.

## Scope semantics — scope axis

| Option | Description | Selected |
|--------|-------------|----------|
| CVE × scope | Pin a CVE to a target (finding / asset / asset-group) | ✓ |
| Whole-target blanket | Exclude ALL findings on a target regardless of CVE (like asset `is_ignored`) | |
| Both, selectable | Let the analyst choose CVE-scoped or blanket | |

**User's choice:** CVE × scope.
**Notes:** Matches analyst reasoning and today's ignore-CVE; blanket risks silently hiding unrelated new criticals.

---

## FP vs accept-risk + expiry — record type

| Option | Description | Selected |
|--------|-------------|----------|
| One record + `type` enum | Single table, `type IN (FALSE_POSITIVE, ACCEPTED_RISK)`; shared machinery | ✓ |
| Two distinct flows | Separate models/endpoints | |

**User's choice:** One record + `type` enum.

## FP vs accept-risk + expiry — expiry applicability

| Option | Description | Selected |
|--------|-------------|----------|
| Mandatory on both | Both types require expiry; even FP resurfaces to re-confirm | ✓ |
| Only accept-risk expires | FP treated as effectively permanent | |

**User's choice:** Mandatory on both.
**Notes:** Serves the goal's "never permanently silenced." Per-type default windows left to planning.

## FP vs accept-risk + expiry — SLA clock on resurface

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude accepted period | Excepted duration doesn't count against SLA; due date shifts; re-enters for re-evaluation | ✓ |
| Recompute from original detection | SLA from `first_detected_at`; may appear instantly breached | |
| Restart clock on resurface | Treat resurface as new detection; resets aging | |

**User's choice:** Exclude accepted period.
**Notes:** Truer to "resurface for a decision." Cost: Phase 36 read-time SLA subtracts active-exception time.

## FP vs accept-risk + expiry — revocation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, audited, immediate resurface | Analyst can revoke early; finding re-enters immediately; audited | ✓ |
| No early revocation | Exceptions run to expiry only | |

**User's choice:** Yes, audited, immediate resurface.
**Notes:** Mirrors existing unignore/unsuppress.

---

## Risk-score exclusion

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude from risk score too | Active exception drops finding from `compute_risk_scores` / asset exposure / heat | ✓ |
| Queues + SLA only, keep risk score | Excepted findings still count toward exposure | |

**User's choice:** Exclude from risk score too.
**Notes:** Honors EXC-02's "excluded from dashboards." Cost: the v4.0 risk-score computation learns the active-exception join (read-only consumer).

## Expiry input & cap

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute date + max cap | Explicit date, validated future + hard cap (e.g. ≤1yr) | ✓ |
| Preset durations + cap | Presets (30/60/90/180d), server computes date; capped | |
| Absolute date, no cap | Free date, only "must be future" | |

**User's choice:** Absolute date + max cap.
**Notes:** Cap enforces "never permanently silenced" at the data layer. Exact cap value → planning.

## Overlap precedence

| Option | Description | Selected |
|--------|-------------|----------|
| OR + latest expiry governs | Covered if ANY active exception matches; resurfaces when last-expiring lapses; revoking one leaves others in force | ✓ |
| Most-specific wins | Finding-level overrides group-level (precedence by granularity) | |

**User's choice:** OR + latest expiry governs.
**Notes:** Simple, safe, matches the compute-on-read join.

## Expiring-soon visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Passive indicator only | List shows expiring-soon/days-remaining badge + expiry sort/filter; no push | ✓ |
| Nothing this phase | Defer even passive visibility | |

**User's choice:** Passive indicator only.
**Notes:** Active push (Slack/email/digest) explicitly deferred to Phase 40 (Proactive Alerting).

---

## Claude's Discretion

- `exceptions` table schema, column names, `type`/scope enums, indexes, Alembic migration structure.
- Exact scope-match SQL and how the active-exception join is factored (shared helper vs per-consumer joins).
- Exact SLA-subtraction implementation within `sla_tier_service` (D-16).
- Whether the expiry-driven resurface writes a lazy-on-read audit row (recommended) or is silent (no actor).
- Exact expiry max-cap value and any per-type default windows.
- The exception form + list UI — deferred to `/gsd-ui-phase` / UI-SPEC.
- Full enumeration of every read path that must learn the exclusion join (research sweep).

## Deferred Ideas

- Legacy suppress consolidation (rewire `/cve/ignore`, `/remediations/suppress`, asset `is_ignored`) — future phase.
- Two-step pending→approved approval with separation of duties.
- Active push for expiring exceptions — Phase 40.
- Frozen-snapshot scoping.
- Free-text / external approver.
- Most-specific-wins overlap precedence.
- Exception-form / list visual design — `/gsd-ui-phase`.
