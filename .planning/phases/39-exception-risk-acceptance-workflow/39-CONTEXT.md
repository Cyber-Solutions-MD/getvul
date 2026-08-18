# Phase 39: Exception & Risk-Acceptance Workflow - Context

**Gathered:** 2026-08-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn today's **ad-hoc suppress flags** into **first-class, governed exception records**.
An analyst can mark a finding / asset / asset-group as **false-positive** or **accept-risk**
via a form that requires a justification, a named approver, an explicit scope, and a
**mandatory expiry**. While an exception is active, the matched finding(s) drop out of active
work queues, SLA timers, and risk-scored dashboards — and when the exception expires, the
finding **auto-resurfaces** into the active queue with no manual re-trigger. Delivers
EXC-01..04.

This is a *how-to-implement* boundary. The building blocks already exist (a `SUPPRESSED` /
`FALSE_POSITIVE` status the read paths already skip, the `/cve/{id}/ignore` +
`/remediations/{id}/suppress` ad-hoc paths, asset `is_ignored`, `audit()`, `require_analyst`,
the Phase 36 read-time SLA engine, the v4.0 risk-score computation). This phase adds a
**new governed `exceptions` record** as the source of truth and wires **compute-on-read
exclusion** on top of the existing consumers.

**In scope:**
- A new `exceptions` table (justification, approver, scope, type, expiry) + grant / list /
  revoke endpoints (EXC-01).
- Compute-on-read exclusion: active exceptions remove matched findings from active queues,
  SLA timers, and risk-scored dashboards until expiry (EXC-02).
- Every grant / revoke audited with who / why / scope / expiry (EXC-03).
- Expired exceptions auto-resurface via the compute-on-read join — no scheduler, no
  re-trigger (EXC-04).
- A passive "expiring soon" indicator + expiry sort/filter in the exceptions list.

**Explicitly NOT this phase:**
- **Retiring / rewiring the legacy suppress paths** (`/cve/ignore`, `/remediations/suppress`,
  asset `is_ignored`) — kept as-is; exclusion is additive (D-02). A future consolidation phase.
- **A pending→approved multi-user approval state machine** — approval is recorded attribution,
  single action (D-07).
- **Active push / notification of expiring exceptions** (Slack / email / digest) — deferred to
  Phase 40 (Proactive Alerting). Only a passive list indicator here (D-18).
- **Frozen-snapshot scoping** — scope is live-membership by predicate (D-10).
- **Re-deriving `remediation_id` / owner routing / the v4.0 risk score** — all consumed
  read-only; exceptions only *filter* them (lane discipline).
- **The exception-form / list visual design** — left to `/gsd-ui-phase` (UI-SPEC).
</domain>

<decisions>
## Implementation Decisions

### Exclusion model & source of truth (EXC-01 / EXC-02)

- **D-01 — New `exceptions` table is the source of truth; exclusion is a compute-on-read
  join.** Granting an exception does **not** permanently flip finding status. Exclusion is
  derived at read time by joining findings against *active (non-expired)* exceptions. Chosen
  over status-flip (keeps governance in one place; no drift between a status column and a
  governance row; survives scanner re-sync untouched). — **Reversibility:** costly — switching
  to a status-flip model later means introducing a re-flip path and rewiring every exclusion
  consumer that learned the join.
- **D-02 — Additive to the legacy suppress paths.** The existing `/cve/{id}/ignore`,
  `/remediations/{id}/suppress`, and asset `is_ignored` stay as-is. Exclusion becomes the union:
  a finding is excluded if `status IN (SUPPRESSED, FALSE_POSITIVE)` **OR** an active exception
  matches it. No migration of shipped endpoints/tests this phase. Legacy consolidation is noted
  for a future phase.
- **D-03 — Grant only on actionable (OPEN / IN_PROGRESS) findings.** Accept-risk / false-positive
  only makes sense on an active finding; granting against a `REMEDIATED` item is rejected /
  no-op. Matches how `/cve/ignore` already targets `status IN (OPEN, IN_PROGRESS)`.
- **D-04 — EXC-04 auto-resurface is free via compute-on-read.** An exception is "active" only
  while `now < expiry`. Once expired, the active-exception join stops matching and the finding
  reappears in every consumer automatically — no scheduler tick, no re-flip, no manual
  re-trigger. Same discipline as Phase 38 D-07/D-19 and Phase 36's read-time SLA.

### Record shape & types (EXC-01)

- **D-05 — One `exceptions` table with a `type` enum `{FALSE_POSITIVE, ACCEPTED_RISK}`.** Same
  form, scope, approver, expiry, audit, and exclusion machinery for both; `type` is metadata
  driving labeling (and optionally different default expiry windows). Least surface area;
  mirrors the shared `VulnStatus` enum already carrying both concepts. — **Reversibility:**
  costly — splitting into two models later is a migration + endpoint fork.
- **D-06 — Justification, approver, scope, and expiry are all mandatory — for both types.**
  The governed record is defined by these required fields (contrast: today's bare-reason
  suppress). No optional-approver, no optional-expiry.

### Approval & RBAC (EXC-01 / EXC-03)

- **D-07 — Recorded-attribution, single-action grant (no pending→approved state machine).** The
  granting analyst fills a required **approver** field and the exception is created + audited in
  one action. Governance comes from the mandatory fields + the audit trail, not a separate
  approval turn. A full two-step separation-of-duties flow was considered and rejected as
  larger than EXC-01 scopes.
- **D-08 — Approver is a required tenant-user reference (FK), not free text.** The audit "who"
  resolves to a real accountable identity and exceptions are listable by approver. (Assumes the
  approver is a GetVul user; out-of-band external approvers are out of scope this phase.)
- **D-09 — `require_analyst` for grant / list-write / revoke.** Consistent with every existing
  suppress/ignore write. Reads follow the existing viewer/analyst pattern. Exceptions are an
  analyst triage workflow, not admin config.

### Scope semantics (EXC-01)

- **D-10 — Scope pins a CVE × target: finding / asset / asset-group.** e.g. "accept-risk
  CVE-2024-x on asset-group Lab-hosts." Not a blanket whole-target exception (which would hide
  unrelated new criticals on an "excepted" asset). Matches how analysts reason and how
  `/cve/ignore` already scopes by CVE.
- **D-11 — Live membership.** An exception is a scope *predicate*; it covers all matching
  findings — present AND future — until expiry. A later scan that re-detects the CVE on a
  group asset (or a newly-joined group member) stays excluded automatically. Mirrors Phase 38
  D-03; the compute-on-read join handles it for free. — **Reversibility:** costly — a frozen
  snapshot later means a membership table + re-granting on every recurrence.
- **D-12 — Overlap = OR semantics; latest expiry governs resurface.** A finding matched by
  multiple active exceptions (e.g. finding-level + asset-group-level) is excluded if ANY of them
  is active, and resurfaces only when the **last-expiring** covering exception lapses. Revoking
  one exception while another still covers keeps the finding excluded. No most-specific-wins
  precedence logic.

### Expiry (EXC-02)

- **D-13 — Mandatory expiry on BOTH types.** Even a false-positive expires and resurfaces so
  someone re-confirms it's still bogus — directly serving the goal's "nothing silently ignored
  forever." (Defaults may differ per type — e.g. FP longer, accept-risk shorter — exact windows
  → planning.)
- **D-14 — Absolute expiry date, validated future + hard max cap.** The analyst picks an explicit
  date; the server rejects past dates and dates beyond a hard ceiling (e.g. ≤ 1 year — exact cap
  → planning) so a 2099 date can't quietly defeat "never permanently silenced."

### Exclusion surface (EXC-02)

- **D-15 — Exclusion is comprehensive: active queues + SLA timers + risk-scored dashboards.**
  An active exception removes the matched finding from the active vuln list/queue
  (`list_vulnerabilities`), the SLA engine (`resolve_state_for_vuln`), AND the v4.0 risk score
  (`compute_risk_scores` / asset `risk_exposure_score`) — so dashboards and heat reflect only
  un-excepted risk. Honors EXC-02's "excluded from … dashboards." Each is a read-only consumer
  learning the active-exception join (lane-safe — no re-derivation). — **Reversibility:** costly
  — the join touches several read paths; narrowing later means auditing each consumer.
- **D-16 — The excepted duration does NOT count against the SLA clock.** On resurface, the SLA
  due date is shifted by how long the finding was under an active exception, so it re-enters for
  re-evaluation rather than instantly breached. `sla_tier_service` (`compute_sla_state` /
  `resolve_state_for_vuln`) subtracts active-exception time. — **Reversibility:** costly —
  changes the Phase 36 read-time SLA computation.

### Revocation & audit (EXC-01 / EXC-03)

- **D-17 — Early revocation allowed, audited, immediate resurface.** An analyst can revoke an
  exception before expiry; the finding immediately re-enters queues / SLA / dashboards and the
  revocation is audited (who / when). Mirrors the existing unignore/unsuppress paths.
- **D-18 — Every mutation routes through `audit()` (tenant-scoped, fail-closed).** Grant audit
  payload records type / scope / approver / justification / expiry (EXC-03's who/why/scope/expiry);
  revoke records who/when. Same discipline as Phase 36/37/38 status writes.

### Visibility

- **D-19 — Passive "expiring soon" indicator only.** The exceptions list shows a
  days-remaining / "expiring soon" badge and is sortable/filterable by expiry. Active push
  (Slack / email / digest) is explicitly deferred to Phase 40 (Proactive Alerting).

### Claude's Discretion (planner / researcher / gsd-ui-phase decide)
- `exceptions` table schema, column names, the `type`/scope enums, indexes, and the Alembic
  migration structure.
- The exact scope-match SQL for finding / asset / asset-group and how the active-exception join
  is factored — a single shared helper/subquery that each consumer calls vs. per-consumer joins
  (a shared "effective exclusion" seam is preferable for consistency).
- The exact SLA-subtraction implementation for D-16 within `sla_tier_service`.
- Whether the expiry-driven resurface writes a lazy-on-read audit row (like Phase 38 D-19,
  recommended for a complete trail) or is silent — there is no actor, so it's optional.
- The exact expiry max-cap value (D-14) and any per-type default windows (D-13).
- The exception form + list UI (grant / list / revoke, expiring-soon badge) — defer to
  `/gsd-ui-phase` / UI-SPEC and the `sketch-findings-getvul` design system.
- The precise enumeration of every read path that must learn the exclusion join (D-15) — the
  known ones are listed under Integration Points; research should sweep for any others
  (remediation grouped view, campaign denominator, search).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap (scope source of truth)
- `.planning/REQUIREMENTS.md` §EXC-01..04 (lines 49-54) — the four locked requirements this
  phase satisfies; §"Auditability" (line 23) requires every mutating action to audit.
- `.planning/ROADMAP.md` → "Phase 39: Exception & Risk-Acceptance Workflow" (line 158) — goal +
  four success criteria.

### Existing suppress / ignore precedent — extend, do NOT retire (D-01/D-02)
- `backend/app/vulnerabilities/models.py:24` — `VulnStatus` enum (`SUPPRESSED`,
  `FALSE_POSITIVE` already exist; the read paths already skip them).
- `backend/app/vulnerabilities/router.py:525` — `POST /cve/{cve_id}/ignore` (flips
  `OPEN/IN_PROGRESS → SUPPRESSED` + reason + `compute_risk_scores` + `audit`); `:569`
  `/cve/{cve_id}/unignore`; `:811` `/remediations/{remediation_id}/suppress`; `:874`
  `/remediations/{remediation_id}/unsuppress`.
- `backend/app/assets/models.py:74-76` — asset `is_ignored` / `ignored_at` / `ignored_reason`
  (asset-level ad-hoc ignore precedent); `backend/app/assets/router.py:534` sets it.
- `backend/app/assets/models.py:171` — `AssetGroupExposureOverride` (group-scoped override
  precedent + most-recently-updated-wins tiebreak; reference for group-scope handling).

### Exclusion consumers that must learn the active-exception join (D-15/D-16)
- `backend/app/vulnerabilities/service.py:130` — `list_vulnerabilities` (the active queue;
  attaches read-time `sla_state`/`sla_due_at`); `:300` `get_vulnerability`.
- `backend/app/vulnerabilities/sla_tier_service.py` — `resolve_state_for_vuln`,
  `compute_sla_state`, `run_sla_tier_pass` (Phase 36 read-time SLA engine; D-16 subtracts
  active-exception time here).
- `backend/app/assets/risk_score.py:91` — `compute_risk_scores` (filters
  `status IN (OPEN, IN_PROGRESS)` at `:126`; D-15 must also exclude active-excepted findings
  from `risk_exposure_score`).
- `backend/app/vulnerabilities/remediation_service.py:14` — `_base_open_vulns` /
  `get_remediations_grouped` (remediation view; already has a `show_suppressed` axis — a natural
  place to fold exception filtering).
- `backend/app/campaigns/service.py` — campaign denominator (Phase 38 D-18 already filters
  `OPEN/IN_PROGRESS/REMEDIATED`; confirm excepted findings drop out consistently).

### Scope resolution (D-10/D-11)
- `backend/app/assets/models.py:141` `AssetGroup`; `:155` `AssetGroupMember`
  (`group_id`/`asset_id`) — asset-group scope resolves through this membership (live).
- `backend/app/vulnerabilities/models.py` — `Vulnerability.cve_id` / `asset_id` /
  `remediation_id` / `status` (the fields a scope predicate matches on).

### Audit + RBAC + router registration (EXC-03 / D-09 / D-18)
- `backend/app/audit.py:143` — `audit()` (tenant-scoped, fail-closed) for every grant/revoke.
- `backend/app/auth/rbac.py:50-52` — `require_viewer` / `require_analyst` / `require_admin`.
- `backend/app/main.py:271` `create_app()`; `:319` campaigns router registration under
  `/api/v1/*` — the pattern a new exceptions router follows.

### Prior-phase decisions this phase leans on (carry-forward)
- `.planning/phases/38-remediation-campaigns/38-CONTEXT.md` §D-03 (live membership), §D-07/D-19
  (compute-on-read, lazy-on-read audit), §D-18 (SUPPRESSED/FALSE_POSITIVE excluded from the
  campaign denominator).
- `.planning/phases/36-remediation-sla-engine-escalation/36-01-SUMMARY.md` — the SLA engine
  surface (`sla_tier_service.py`, read-time `sla_state`/`sla_due_at`) D-16 modifies.

### Frontend (UI hint: yes)
- `.claude/skills/sketch-findings-getvul/` — design system (status / SLA visual language, state
  patterns, copy voice) — MUST follow for the exception form + list.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `VulnStatus.SUPPRESSED` / `FALSE_POSITIVE` + the read paths that already skip them — the
  legacy exclusion signal the new exception join is unioned with (D-02).
- `audit()` — every grant/revoke audits through it (D-18); grant payload carries
  who/why/scope/expiry (EXC-03).
- `require_analyst` — RBAC for all exception writes (D-09).
- `AssetGroupMember` — asset-group scope resolves through existing group membership (D-11).
- `resolve_state_for_vuln` / `compute_sla_state` — the read-time SLA seam D-16 hooks into.
- `remediation_service._base_open_vulns` `show_suppressed` axis — precedent for a
  filter-on-read exclusion parameter the exception join can extend.

### Established Patterns
- **Compute-on-read exclusion / lazy-on-read state** (Phase 36 SLA, Phase 38 D-07/D-19) — the
  exact discipline D-01/D-04 use so expiry auto-resurfaces with no scheduler.
- **Live membership by predicate** (Phase 38 D-03) — reused for scope matching (D-11).
- **Read-only lane discipline** — every exclusion consumer *filters* existing data; nothing
  re-derives `remediation_id` / owner routing / the v4.0 risk score.
- **Alembic migrations** (47+ existing) — the new `exceptions` table follows the established flow.

### Integration Points
- Grant/revoke endpoints → `exceptions` table + `audit()` + `require_analyst`.
- Active-exception join → `list_vulnerabilities`, `sla_tier_service` (with duration subtraction),
  `compute_risk_scores`, remediation grouped view, campaign denominator (D-15/D-16).
- Scope predicate → `Vulnerability.cve_id`/`asset_id` + `AssetGroupMember` (D-10/D-11).
- Expiry → compute-on-read active flag; expired exceptions simply stop matching the join (D-04).
- Exceptions list → passive "expiring soon" badge + expiry sort/filter (D-19).

</code_context>

<specifics>
## Specific Ideas

- The exception record is the governed upgrade of today's bare-reason suppress: justification +
  named tenant-user approver + explicit CVE×scope + mandatory capped expiry, all required.
- Exclusion is derived, not stored on the finding — so a scanner re-detecting an excepted CVE
  changes nothing (the finding stays OPEN under the hood and the join still covers it).
- "Never silently ignored forever": both false-positives and accept-risks expire, capped at a
  hard ceiling, and resurface automatically for a fresh decision.
- On resurface, an item is NOT instantly breached — the accepted period is subtracted from its
  SLA clock so it re-enters for re-evaluation, not as an escalation storm.

</specifics>

<deferred>
## Deferred Ideas

- **Legacy suppress consolidation** — rewiring `/cve/ignore`, `/remediations/suppress`, asset
  `is_ignored` onto the exception path (one unified exclusion signal). Rejected here as scope
  creep (D-02); revisit as its own phase.
- **Two-step pending→approved approval** (separation of duties, requester ≠ approver) — rejected
  for D-07's single-action attribution; revisit if a real approval queue is requested.
- **Active push for expiring exceptions** (Slack / email / digest) — belongs to Phase 40
  (Proactive Alerting); only a passive list indicator here (D-19).
- **Frozen-snapshot scoping** — a later phase could add snapshot scopes if live membership
  (D-11) proves too broad.
- **Free-text / external approver** — D-08 requires a tenant-user reference; external-approver
  support could come later.
- **Most-specific-wins overlap precedence** — D-12 chose OR semantics; add precedence only if
  analysts need "override the blanket for this one box" explicitly.
- **Exception-form / list visual design** — handled by `/gsd-ui-phase` (UI-SPEC), not a later
  milestone; noted so planning doesn't invent it.

None of these were scope creep into Phase 39 — discussion stayed within the four success criteria.

</deferred>

---

*Phase: 39-exception-risk-acceptance-workflow*
*Context gathered: 2026-08-18*
