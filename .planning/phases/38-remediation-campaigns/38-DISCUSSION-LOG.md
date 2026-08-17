# Phase 38: Remediation Campaigns - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-17
**Phase:** 38-remediation-campaigns
**Areas discussed:** Grouping unit, Ticket granularity, Membership, Campaign MTTR, Existing-ticket handling, Owner-less findings, Liveness, Lifecycle, New-member ticketing, Reopen interaction, Uniqueness, RBAC

---

## Grouping unit (CAMP-01)

| Option | Description | Selected |
|--------|-------------|----------|
| 1:1 with a remediation group | Campaign = one existing remediation_id group; reuses get_remediations_grouped | ✓ |
| User-defined, can span multiple fixes | Explicit new grouping bundling several remediation_ids / CVEs | |
| CVE-centric grouping | Keyed on shared CVE across assets even if remediation_id differs | |

**User's choice:** 1:1 with a remediation group (→ D-01)
**Notes:** Keeps the campaign a thin persisted wrapper over existing grouping machinery; "one action" = launch from the remediation view.

---

## Ticket granularity (CAMP-02)

| Option | Description | Selected |
|--------|-------------|----------|
| One ticket per owner | One ticket per assignee covering all their affected assets | ✓ |
| One ticket per host/asset | Mirrors create_host_ticket; more tickets, finer tracking | |
| Analyst chooses at create time | Expose per-owner vs per-host toggle | |

**User's choice:** One ticket per owner (→ D-04)
**Notes:** Best matches "bulk-assign respecting owner routing"; fewest tickets; reuses N-rows-share-one-URL linkage grouped by assignee.

---

## Membership

| Option | Description | Selected |
|--------|-------------|----------|
| Live / dynamic membership | Matching findings (incl. newly scanned) join automatically | ✓ |
| Static snapshot at creation | Membership frozen to launch-time set | |
| Snapshot + manual add-in | Frozen by default, analyst can pull new ones in | |

**User's choice:** Live / dynamic membership (→ D-03)
**Notes:** Burndown reflects true current exposure; denominator can grow.

---

## Campaign MTTR (CAMP-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Avg of member finding MTTRs | Average of per-finding RemediationEvent durations | ✓ |
| Campaign wall-clock | campaign_created → last member remediated | |
| Show both | Surface avg-member + wall-clock | |

**User's choice:** Avg of member finding MTTRs (→ D-12)
**Notes:** Consistent with Phase 36 tier MTTR; reads the same RemediationEvent data.

---

## Scope (grouping + membership reconciliation)

| Option | Description | Selected |
|--------|-------------|----------|
| Whole group, always | Campaign = all findings sharing remediation_id, present + future; no subset UI | ✓ |
| Optional asset-subset at launch | Analyst narrows to specific assets/owners | |

**User's choice:** Whole group, always (→ D-02)
**Notes:** Campaign identity = remediation_id, not a frozen asset list — coherent with live membership.

---

## Existing tickets (CAMP-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt existing, create only for the rest | Fold live-ticketed findings in as-is; ticket only un-ticketed ones | ✓ |
| Always create fresh campaign tickets | New tickets regardless of prior linkage | |

**User's choice:** Adopt existing, create only for the rest (→ D-06)
**Notes:** Reuses dedup-by-URL; avoids duplicate tickets.

---

## No owner (CAMP-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Unassigned ticket in default project | Ticket created with no assignee in default project/board | ✓ |
| Surface as a pre-create review list | Show owner-less findings before create | |
| Skip + report | Don't ticket; list as 'needs owner' | |

**User's choice:** Unassigned ticket in default project (→ D-08)
**Notes:** Nothing silently dropped; analyst triages assignment later.

---

## Liveness (CAMP-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Compute-on-read | Aggregate statuses + RemediationEvent at request time; no snapshot | ✓ |
| Scheduler-refreshed snapshot | Persist progress columns updated on scheduler tick | |

**User's choice:** Compute-on-read (→ D-07)
**Notes:** Mirrors current ticket-stats re-aggregation; always current; simplest.

---

## Lifecycle (CAMP-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-complete + manual close | Auto-complete at 100% rescan-verified; analyst can close early; both audited | ✓ |
| Manual close only | Stays open until explicit close | |
| Discuss it now | Deeper dive on close semantics | |

**User's choice:** Auto-complete + manual close (→ D-13)
**Notes:** Covers CAMP-04's 'close' action.

---

## New members (live-join ticketing)

| Option | Description | Selected |
|--------|-------------|----------|
| Analyst re-runs bulk-create | Newcomers counted but un-ticketed until analyst re-runs (adopt + ticket new) | ✓ |
| Auto-ticket on join | Joining findings auto-ticketed immediately | |

**User's choice:** Analyst re-runs bulk-create (→ D-10)
**Notes:** Bulk external ticket creation stays explicit + human-in-the-loop.

---

## Reopen interaction (Phase 37)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-reactivate | Reopened finding flips campaign complete→active (compute-on-read) | ✓ |
| Stay closed, exclude reopened | Closed campaign immutable; reopened finding is new exposure | |

**User's choice:** Auto-reactivate (→ D-14)
**Notes:** Consistent with live membership + Phase 37 reopen-on-recurrence.

---

## Uniqueness

| Option | Description | Selected |
|--------|-------------|----------|
| One active campaign per group | Unique (tenant, remediation_id); relaunch opens existing | ✓ |
| Allow multiple | No constraint | |

**User's choice:** One active campaign per group (→ D-11)
**Notes:** Prevents overlapping membership / double-counted tickets; DB partial unique constraint.

---

## RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| Analyst (match ticketing) | create/bulk-assign/close require require_analyst | ✓ |
| Admin for bulk/close, analyst reads | Elevate bulk blast-radius to Admin+ | |

**User's choice:** Analyst (match ticketing) (→ D-16)
**Notes:** Campaigns are a ticketing workflow, consistent with all existing ticketing writes.

---

## Claude's Discretion

- Campaign table schema / column names / status enum / Alembic migration structure (incl. D-11 partial unique constraint).
- New `app/campaigns/` module vs under `app/ticketing/`.
- Exact compute-on-read aggregation SQL (reuse get_mttr_by_tier / ticket-stats shapes).
- How "adopt existing ticket" detects a live link (reuse dedup-by-URL path).
- Campaign-view UI shape — deferred to /gsd-ui-phase + sketch-findings-getvul.

## Deferred Ideas

- Cross-CVE / multi-fix campaigns (rejected; keeps D-01 1:1).
- Launch-time asset-subset scoping (rejected via D-02).
- Auto-ticket-on-join as a per-campaign opt-in (rejected via D-10).
- Scheduler-refreshed progress snapshot (rejected via D-07).
- Campaign-view visual design (owned by /gsd-ui-phase).
