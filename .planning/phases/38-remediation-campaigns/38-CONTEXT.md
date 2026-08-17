# Phase 38: Remediation Campaigns - Context

**Gathered:** 2026-08-17
**Status:** Ready for planning

<domain>
## Phase Boundary

An analyst acts on a whole class of findings **at once** — group findings sharing a
fix across every affected asset/owner into one persisted **campaign**, bulk-create/assign
tickets respecting each finding's existing owner routing, and watch the campaign burn
down live (open / in-progress / done %, campaign MTTR) — instead of ticketing one finding
at a time. Delivers CAMP-01..04.

This is a *how-to-implement* boundary. ~80% of the plumbing already exists (remediation
grouping, per-owner ticket linkage, owner routing, MTTR capture, audit) — this phase
**persists an explicit campaign grouping** on top of it and adds live progress + lifecycle.

**In scope:**
- Group findings sharing a fix into a campaign in one action, from a dedicated campaign view (CAMP-01).
- Bulk-create/assign tickets for a campaign, reusing existing owner routing verbatim (CAMP-02).
- Live per-campaign progress + campaign MTTR (CAMP-03).
- Audit every campaign action — create, bulk-assign, close (CAMP-04).

**Explicitly NOT this phase:**
- Exception / risk-acceptance workflow — Phase 39.
- Proactive alerting / digests — Phase 40.
- New scanners, patch-deployers, or any change to how `remediation_id` / owner routing /
  the v4.0 risk score are *derived* (all consumed, never re-derived — lane discipline).
- Real-time push; "live" = compute-on-read at view time (see D-07).
- The campaign-view visual design — left to `/gsd-ui-phase` (UI-SPEC).
</domain>

<decisions>
## Implementation Decisions

### Campaign grouping & scope (CAMP-01)

- **D-01 — Campaign is 1:1 with an existing remediation group.** A campaign wraps one
  `Vulnerability.remediation_id` group (the shared patch/product/action GetVul already
  groups by via `get_remediations_grouped()`). Analyst launches a campaign directly from
  the remediation view — "one action." No new cross-CVE / multi-fix grouping engine.
- **D-02 — Whole group, always (no asset subset).** A campaign is *every* finding sharing
  that `remediation_id` — present and future. There is no launch-time subset selection;
  scoping to specific assets is out. This keeps D-01 + live membership (D-03) coherent:
  the campaign's identity is the `remediation_id`, not a frozen asset list.
- **D-03 — Live / dynamic membership.** Any finding matching the campaign's `remediation_id`
  is a member — including findings a later scan discovers on a newly-seen asset. The
  denominator can grow; burndown reflects true current exposure. — **Reversibility:** costly —
  switching to a frozen snapshot later means introducing a membership table and rewiring
  every progress/MTTR read that currently derives membership from `remediation_id`.
- **D-11 — One active campaign per (tenant, remediation_id).** Enforce uniqueness. Launching
  a campaign on a group that already has an active one **opens the existing campaign** rather
  than creating a duplicate. Prevents overlapping membership / double-counted tickets. —
  **Reversibility:** one-way — enforced by a DB unique constraint (partial, on active status)
  in the campaign migration; relaxing it later is a migration + dedup of any duplicates created.

### Bulk ticketing (CAMP-02)

- **D-04 — One ticket per owner.** Each owner gets a single ticket covering all their
  affected assets in the campaign. Best matches "bulk-assign respecting owner routing";
  fewest tickets. Reuses the existing N-rows-share-one-`external_ticket_url` linkage,
  grouped by assignee.
- **D-05 — Owner routing is reused verbatim, never re-derived (CAMP-02 constraint).** Assignee
  comes from the existing inline derivation (`asset.assigned_user` / `asset.mdm_details`
  Humaans email) in `ticketing/service.py`. No campaign-level re-derivation; no manual owner
  override silently dropped.
- **D-06 — Adopt existing tickets; create only for the rest.** Findings already linked to a
  live ticket (from single-finding ticketing or an automation rule) are folded into campaign
  tracking as-is — no duplicate. Tickets are created only for un-ticketed findings. Reuses the
  existing dedup-by-URL logic.
- **D-08 — Owner-less findings → unassigned ticket in the connector's default project.** A
  finding with no derivable owner still gets a ticket (unassigned, default project/board) —
  nothing silently dropped (CAMP-02 "no findings silently dropped"). Analyst triages assignment
  later.
- **D-10 — New live-joined members are NOT auto-ticketed.** A finding that joins a live
  campaign after launch is counted in progress but stays un-ticketed until the analyst
  **re-runs bulk-create** (which adopts existing per D-06 and tickets only the newcomers).
  Bulk external ticket creation stays an explicit, audited, human-in-the-loop action — never
  fires automatically on membership change.

### Live progress & MTTR (CAMP-03)

- **D-07 — Compute-on-read.** Progress (open / in-progress / done %) and campaign MTTR are
  aggregated from member finding statuses + `RemediationEvent` rows at request time — no
  persisted progress columns, no scheduler refresh path. Mirrors how ticket stats
  re-aggregate today. Always current; simplest.
- **D-09 — "Done" = rescan-verified REMEDIATED only (carry-forward, Phase 37 D-03).** A
  campaign member counts as done/remediated **only** when the scanner re-scan verified it
  (status REMEDIATED via `mark_vulnerability_remediated`). A done/closed ticket drives the
  finding to IN_PROGRESS, never closes it — so "% remediated" tracks real fix verification,
  not ticket state. In-progress % keys off status IN_PROGRESS.
- **D-12 — Campaign MTTR = average of member finding MTTRs.** Average of the per-finding
  durations (`first_detected_at → remediated_at`) from `RemediationEvent` rows over remediated
  members. Consistent with Phase 36's tier MTTR; reads the same data, never re-derives it.

### Lifecycle & audit (CAMP-04)

- **D-13 — Auto-complete + manual early close.** A campaign auto-marks **complete** when 100%
  of its (live) members are rescan-verified remediated; an analyst may also **manually close
  early**. Both transitions are audited.
- **D-14 — Auto-reactivate on recurrence (Phase 37 D-04 interaction).** If a completed
  campaign's member finding reopens via Phase 37 reopen-on-recurrence, it is OPEN again and
  still matches the `remediation_id`, so with compute-on-read (D-07) the campaign flips
  complete→active automatically and its % drops. Campaign status is derived, not a frozen
  terminal state.
- **D-15 — Every campaign action audited via the existing `audit()` helper.** create,
  bulk-assign (each run), and close route through `app/audit.py::audit` (tenant-scoped,
  fail-closed) — same discipline as Phase 36/37 status writes.

### RBAC

- **D-16 — Analyst+ for all campaign writes.** create / bulk-assign / close require
  `require_analyst`, consistent with every existing ticketing write. Campaigns are a
  ticketing workflow, not admin config. Reads follow the existing viewer/analyst pattern.

### Research open-question resolutions (2026-08-17, post-RESEARCH.md)

- **D-17 — Manual early-close is sticky (resolves RESEARCH Q2/A2).** D-14 auto-reactivation on
  recurrence applies ONLY to campaigns that reached `complete` by derived 100%-remediation. A
  campaign the analyst **manually closed early** stays `closed` even if a member finding recurs
  via Phase 37 reopen-on-recurrence — `closed` is a stored terminal status reflecting the
  analyst's explicit "stop tracking" decision, not a derived state. Implication: campaign status
  is derived (active↔complete via compute-on-read, D-07) EXCEPT the stored terminal `closed`
  status, which suppresses reactivation. A member recurring under a closed campaign is simply an
  un-campaigned open finding until/unless a new campaign is launched on that `remediation_id`.
- **D-18 — SUPPRESSED / FALSE_POSITIVE excluded from the campaign denominator.** (Resolves
  RESEARCH Q4/A5.) Campaign membership + burndown denominator counts only actionable statuses
  (`OPEN` / `IN_PROGRESS` / `REMEDIATED`). SUPPRESSED and FALSE_POSITIVE findings sharing the
  `remediation_id` drop out of the denominator entirely — consistent with how suppression already
  hides them from the remediation view. This is the corrected filter the researcher flagged
  (`_base_open_vulns()` naive reuse would exclude REMEDIATED and read 0% forever); the campaign
  progress query MUST use `OPEN`/`IN_PROGRESS`/`REMEDIATED`, never the bare `_base_open_vulns()`.
- **D-19 — Auto-complete transition audited lazily-on-read (resolves RESEARCH Q1/A1).** The derived
  complete↔active transition is detected + audited lazily when the campaign is read (no new
  scheduler tick — Deferred Ideas rules that out; no inline hook in
  `mark_vulnerability_remediated`/`reopen_vulnerability`). First read that observes 100% derived
  remediation writes the `complete` audit row (idempotent — audit once per transition, not per read).
- **D-20 — Campaigns reuse the BARE `remediation_id` string as `created_by_rule`.** (Resolves
  RESEARCH Q5.) Campaign-created tickets set `created_by_rule = <remediation_id>` (no `"campaign:{id}"`
  prefix) so the existing `create_remediation_ticket()` dedup check and any later `per_remediation`
  automation rule recognize them and cannot double-ticket a campaign's members. Do NOT harden
  `rule_engine.py`'s per-vulnerability dedup this phase — the shared-string convention closes the
  gap for free.

### Claude's Discretion (planner/researcher decide)
- Campaign table schema, column names, status enum values, and the Alembic migration
  structure (including the partial unique constraint for D-11).
- Whether the campaign router is a new `app/campaigns/` module or lives under
  `app/ticketing/` — follow the closest existing module convention.
- Exact aggregation SQL for compute-on-read progress/MTTR (reuse the `get_mttr_by_tier` /
  ticket-stats re-aggregation shapes).
- How "adopt existing ticket" (D-06) detects a live link (by `external_ticket_url` /
  `vulnerability_id` join) — reuse the current dedup path.
- The campaign-view UI shape (list + burndown detail) — defer to `/gsd-ui-phase` /
  UI-SPEC and the `sketch-findings-getvul` design system.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` §CAMP-01..04 — the four locked requirements this phase satisfies.
- `.planning/ROADMAP.md` → "Phase 38: Remediation Campaigns" — goal + 4 success criteria (scope source of truth).

### Prior-phase decisions this phase depends on (carry-forward)
- `.planning/phases/37-two-way-ticket-sync-remediation-verification/37-CONTEXT.md` §D-03/D-04 —
  scanner rescan is the ONLY closure path (D-09 here); reopen-on-recurrence resurrects the same
  finding (D-14 here).
- `.planning/phases/36-remediation-sla-engine-escalation/36-CONTEXT.md` §D-09 —
  `mark_vulnerability_remediated` single-helper discipline + `RemediationEvent` for MTTR.

### Grouping — reuse as the campaign's grouping key (CAMP-01)
- `backend/app/vulnerabilities/remediation_service.py:53` — `get_remediations_grouped()`
  (groups by `remediation_id` / `remediation_action` / `affected_product`); `:150`
  `get_hosts_for_remediation()`; `:208` `get_remediations_for_host()`.
- `backend/app/vulnerabilities/router.py:781` — `GET /remediations/grouped`; `:811`
  `POST /remediations/{remediation_id}/suppress` (existing bulk status write over a group).
- `backend/app/vulnerabilities/models.py` — `Vulnerability.remediation_id` /
  `remediation_action` / `affected_product` (the grouping key); `status` enum.

### Bulk ticketing + owner routing — reuse verbatim (CAMP-02)
- `backend/app/ticketing/service.py:548` — `create_remediation_ticket()` (one external
  ticket over all affected hosts for a `remediation_id`; strongest campaign-like primitive);
  `:358` `create_host_ticket()`; `:163` `create_tickets()`.
- `backend/app/ticketing/service.py:221-230`, `:457-461`, `:567` — inline owner derivation
  from `asset.assigned_user` / `asset.mdm_details["humaans_email"]` (D-05 reuses this).
- `backend/app/ticketing/service.py:668-688` — N-rows-share-one-`external_ticket_url`
  linkage (`external_ticket_id = f"{ref}:{vuln.id}"`, `created_by_rule`) — D-04/D-06 reuse.
- `backend/app/ticketing/models.py:84` — `Ticket.vulnerability_id` is **single** (no
  `vulnerability_ids` array on the model); grouping = multiple rows sharing one URL.
- `backend/app/ticketing/dispatch.py:130-154` — provider/project routing (Asana/Jira/GitHub)
  for the default-project fallback (D-08).
- `backend/app/ticketing/rule_engine.py:183/208` — existing `per_host` / `per_remediation`
  ticket modes (reference for per-owner carve-up).
- `backend/app/connectors/humaans_sync.py:187` — where `mdm_details["humaans_email"]` is set.

### Progress + MTTR — read, never re-derive (CAMP-03)
- `backend/app/vulnerabilities/service.py:374` — `mark_vulnerability_remediated()` (single
  REMEDIATED transition, writes `RemediationEvent`); `:439` `reopen_vulnerability()`;
  `:481` `get_mttr_by_tier()` (aggregation shape to mirror for D-12).
- `backend/app/vulnerabilities/models.py:253` — `RemediationEvent` (`tier_at_remediation`,
  `duration_seconds`, `first_detected_at`, `remediated_at`).

### Audit + RBAC + router registration (CAMP-04, D-16)
- `backend/app/audit.py:143` — `audit()` (tenant-scoped, fail-closed) for every campaign action.
- `backend/app/auth/rbac.py:50-53` — `require_analyst` / `require_viewer` deps.
- `backend/app/main.py:275/309-320` — `create_app()` + router registration under `/api/v1/*`.

### Frontend (UI hint: yes)
- `.claude/skills/sketch-findings-getvul/` — design system (severity / status / SLA visual
  language, state patterns, copy voice) — MUST follow for the campaign view.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_remediations_grouped()` — the campaign grouping key already exists; a campaign is a thin
  persisted wrapper keyed on `remediation_id` (D-01/D-02).
- `create_remediation_ticket()` + the N-rows-share-one-URL linkage — the per-owner bulk-create
  (D-04) is a re-carve of this existing primitive by assignee instead of by host.
- Inline Humaans/`assigned_user` owner derivation — reused verbatim for routing (D-05).
- `mark_vulnerability_remediated` + `RemediationEvent` + `get_mttr_by_tier` — campaign
  progress/MTTR (D-07/D-12) read these directly.
- `audit()` — every campaign action audits through it (D-15).
- `require_analyst` — RBAC for all campaign writes (D-16).

### Established Patterns
- **Dedup-by-URL ticketing** — existing linkage lets D-06 "adopt existing, create only the rest"
  reuse current logic rather than inventing dedup.
- **Compute-on-read aggregation** — ticket stats already re-aggregate rows on read; campaign
  progress (D-07) follows the same no-snapshot approach.
- **Rule engine `per_host` / `per_remediation` modes** — precedent for a per-owner carve-up.
- **Alembic migrations** (47+ existing) — the new campaign table + partial unique constraint
  (D-11) follow the established migration flow.

### Integration Points
- Remediation grouped view → "Start campaign" action (D-01 "one action" entry point).
- Campaign bulk-create → existing ticketing create path (per-owner) + owner routing + dedup.
- Campaign progress/MTTR → member-finding status + `RemediationEvent` reads (no new writer).
- Campaign status is derived (compute-on-read) so it auto-reacts to Phase 37 reopen (D-14).
- Every write → `audit()`; every write route → `require_analyst`.

</code_context>

<specifics>
## Specific Ideas

- Entry point: launch a campaign from the existing remediation grouped view (not a separate
  "build a grouping" flow) — the group *is* the campaign.
- "One ticket per owner" = one external ticket per assignee covering all their campaign assets.
- Campaign detail shows live burndown: open / in-progress / done %, plus avg-member campaign MTTR.
- Re-running bulk-create on a campaign is idempotent for already-ticketed findings (adopt, don't
  duplicate) and only tickets newcomers.

</specifics>

<deferred>
## Deferred Ideas

- **Cross-CVE / multi-fix campaigns** (one campaign spanning several `remediation_id`s /
  CVEs) — rejected for this phase (D-01 keeps it 1:1). Revisit as its own phase if analysts
  need "kill all Log4j across every product" as a single campaign.
- **Launch-time asset-subset scoping** (D-02 rejected it) — a later phase could add scoped
  campaigns if the whole-group default proves too coarse.
- **Auto-ticket-on-join** (D-10 rejected it) — could be a per-campaign opt-in setting later
  if hands-off burndown is requested.
- **Scheduler-refreshed progress snapshot** (D-07 chose compute-on-read) — revisit only if
  compute-on-read becomes a read-scale problem.
- **Campaign-view visual design** — handled by `/gsd-ui-phase` (UI-SPEC), not deferred to a
  later milestone; noted here so planning doesn't try to invent it.

None of these were scope creep into Phase 38 — discussion stayed within the four success criteria.

</deferred>

---

*Phase: 38-remediation-campaigns*
*Context gathered: 2026-08-17*
