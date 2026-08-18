---
phase: 38-remediation-campaigns
reviewed: 2026-08-18T09:55:00Z
depth: deep
files_reviewed: 24
files_reviewed_list:
  - backend/app/campaigns/__init__.py
  - backend/app/campaigns/models.py
  - backend/app/campaigns/schemas.py
  - backend/app/campaigns/service.py
  - backend/app/campaigns/router.py
  - backend/alembic/versions/049_add_campaigns.py
  - backend/app/main.py
  - frontend/src/lib/queries/use-campaigns.ts
  - frontend/src/lib/queries/use-campaign-mutations.ts
  - frontend/src/lib/queries/use-remediations-grouped.ts
  - frontend/src/lib/queries/keys.ts
  - frontend/src/components/campaigns/campaign-status-ribbon.tsx
  - frontend/src/components/campaigns/campaigns-chip-bar.tsx
  - frontend/src/components/campaigns/campaigns-table.tsx
  - frontend/src/components/campaigns/remediations-table.tsx
  - frontend/src/components/campaigns/campaign-burndown-card.tsx
  - frontend/src/app/(authed)/dashboard/campaigns/page.tsx
  - frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx
  - frontend/src/app/(authed)/dashboard/vulnerabilities/remediations/page.tsx
  - frontend/src/components/shell/nav-items.ts
  - frontend/src/components/ui/RiskRing.tsx
findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-08-18T09:55:00Z
**Depth:** deep
**Files Reviewed:** 24 (test files read for coverage cross-reference, not separately findable)
**Status:** issues_found

## Summary

Reviewed the full Phase 38 diff (campaigns persistence + get-or-create, per-owner bulk ticketing,
lifecycle/MTTR, and the frontend campaign list/detail + remediations entry point). Tenant scoping,
RBAC (`require_analyst`/`require_viewer`), audit coverage on every mutating action, and the D-11
race-safe get-or-create were all checked in code and — for the two highest-risk claims — verified
empirically against a live Postgres instance rather than taken on faith:

- **D-11 get-or-create race handling is correct.** Ran a genuine two-connection concurrent race
  against the real `get_or_create_campaign()`; the loser's `IntegrityError` is caught and recovers
  cleanly across 5 repeated runs (`(campaign, True)` / `(campaign, False)`, same row, no duplicate,
  no crash). No finding here.
- **A real, reachable gap exists once a campaign is closed**: neither the backend nor the frontend
  stops ticket creation (or the close endpoint's own re-invocation) from mutating a campaign that
  has already been closed. Both are demonstrated below with a live repro against the actual service
  functions (not simulated).

One BLOCKER and three WARNINGs below. No hardcoded secrets, no `eval`/`innerHTML`/
`dangerouslySetInnerHTML`, no empty catch blocks, and no debug artifacts were found in the phase 38
diff. The pre-existing `jira_client.py` exception-handling gap and the mypy-baseline flake are
already logged in `.planning/phases/38-remediation-campaigns/deferred-items.md` and are not
repeated here.

## Critical Issues

### CR-01: Bulk-assign has no guard against a closed campaign — real tickets get created and vulnerabilities get mutated after "Close campaign"

**File:** `backend/app/campaigns/router.py:203-221` (endpoint), `backend/app/campaigns/service.py:249-372` (`bulk_create_campaign_tickets`), `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx:154,295-312`

**Issue:** Closing a campaign (manual early-close, CAMP-04) is documented and copy-confirmed to the
user as terminal: the close-confirmation dialog says *"they'll stop being tracked here. This can't
be undone from the campaign view."* In practice, a manually-closed campaign that still has
OPEN/IN_PROGRESS members (exactly the scenario the confirmation dialog itself warns about — "N of
M findings aren't rescan-verified yet") can still have tickets bulk-created against it:

- **Backend:** `bulk_assign_campaign` (router.py:203) calls `_get_campaign_or_404` and then runs
  `bulk_create_campaign_tickets` unconditionally — there is no `campaign.closed_at is not None`
  check anywhere in the endpoint or the service function.
- **Frontend:** `canCreateTickets` (page.tsx:154) is `unticketedCount > 0` only — it does **not**
  check `c.status !== 'COMPLETE'`, unlike the "Close campaign" button right below it
  (page.tsx:314's `c.status !== 'COMPLETE' && (...)`). So after a manual close, the status pill
  reads "Complete" while the "Create N tickets" CTA is still rendered, enabled, and fully
  functional.

**Verified live** against the real `bulk_create_campaign_tickets()` (not a mock): seeded a
`Campaign` row with `closed_at=now()`, `close_trigger="manual"` and one `OPEN` member vulnerability,
then called the service function exactly as the router does. Result:
```
bulk_create_campaign_tickets result on a CLOSED campaign: {'created_tickets': 1, 'tickets_linked': 1, 'adopted': 0, 'owners': 1, 'failed_owners': []}
vuln.status after bulk-assign on closed campaign: IN_PROGRESS
```
A real ticket was created (would hit the live Jira/Asana/GitHub connector in production) and the
member vulnerability's status flipped to `IN_PROGRESS`, directly contradicting the closed
campaign's "stopped being tracked" contract. No test in `test_campaigns.py` exercises bulk-assign
against a closed campaign, so this regressed silently.

**Fix:**
```python
# backend/app/campaigns/router.py, inside bulk_assign_campaign, right after _get_campaign_or_404:
campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
if campaign.closed_at is not None:
    raise HTTPException(409, "Campaign is closed. Reopen it before creating tickets.")
```
```tsx
// frontend/.../[id]/page.tsx:154
const canCreateTickets = unticketedCount > 0 && c.status !== 'COMPLETE';
```

## Warnings

### WR-01: `POST /{campaign_id}/close` is not idempotent — re-closing overwrites `closed_at`/`close_trigger` and writes a duplicate audit row

**File:** `backend/app/campaigns/router.py:181-199`

**Issue:** `close_campaign` has no guard against being invoked on an already-closed campaign. It
unconditionally sets `campaign.closed_at = datetime.now(UTC)`, `close_trigger = "manual"`, and
writes a fresh `campaign.close` audit row — every time it's called, regardless of current state.

**Verified live** via two sequential `POST /{id}/close` calls through the real FastAPI test client
against the same campaign:
```
FIRST CLOSE:  200 {'status': 'closed'}   closed_at = 2026-08-18 09:53:51.467463+00:00  trigger=manual
SECOND CLOSE: 200 {'status': 'closed'}   closed_at = 2026-08-18 09:53:51.497000+00:00  trigger=manual (overwritten, later timestamp)
campaign.close audit row count: 2
```
Concretely: (1) the true original `closed_at` timestamp is silently overwritten with a later one,
corrupting lifecycle history; (2) two `campaign.close` audit rows now exist for what should be a
single close event, undermining the audit trail's reliability (CAMP-04's whole purpose); and (3) if
the campaign had instead been `close_trigger="auto_complete"` (D-13) at the time of the stray
re-close, this endpoint would silently flip it to `"manual"`, permanently disabling D-14's
auto-reactivate-on-recurrence behavior for a campaign that was never actually manually closed by a
human decision at that point. This is reachable via any direct API call (no UI gating exists on the
request itself) and via a stale open detail tab whose "Close campaign" button hasn't yet
re-rendered after another session's close/auto-complete.

**Fix:**
```python
campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
if campaign.closed_at is not None:
    raise HTTPException(409, "Campaign is already closed.")
campaign.closed_at = datetime.now(UTC)
...
```

### WR-02: Per-owner ticket-creation loop has no exception isolation — one owner's failure discards tickets already created for earlier owners in the same run

**File:** `backend/app/campaigns/service.py:323-364`

**Issue:** `bulk_create_campaign_tickets` iterates `owner_groups.items()` and only handles the
*graceful* failure path (`client.create()` returning `None` on a bad HTTP status) — it appends to
`failed_owners` and `continue`s. If `client.create()` *raises* instead (the documented pre-existing
`jira_client.py` gap logged in `deferred-items.md`, or any other transport-level exception from any
provider), the exception propagates out of the loop entirely uncaught. Because nothing is
`db.commit()`-ed until the router's final `await db.commit()` (only `db.flush()` happens per-owner,
line 363), the `get_db()` dependency's exception handler rolls back the **whole session** —
discarding the `Ticket` rows and `vuln.status` mutations already flushed for every owner processed
*before* the one that failed, not just the failing owner's own work. A single flaky owner turns a
"create N-1 tickets successfully, fail 1" run into "create 0 tickets, unhandled 500" for the entire
bulk-assign call.

**Fix:** Wrap the `client.create(...)` call (and the ticket-row construction that depends on its
result) in a per-owner `try/except Exception`, appending to `failed_owners` on any failure —
matching the existing graceful-`None` contract instead of only covering it:
```python
try:
    url = await client.create(task_name, notes, **_provider_create_kwargs(provider, owner_email, due_on))
except Exception:
    url = None
if url is None:
    failed_owners.append(owner_email)
    continue
```

### WR-03: Private (`_`-prefixed) cross-module helpers imported from `ticketing/service.py`; ad hoc query key bypasses the single-source `queryKeys` registry

**File:** `backend/app/campaigns/service.py:20`; `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx:104`

**Issue:** Two related encapsulation/consistency gaps:
1. `campaigns/service.py` imports `_extract_ref` and `_provider_create_kwargs` — both underscore-
   prefixed, i.e. explicitly module-private — directly from `app.ticketing.service`. This couples
   campaigns to ticketing's internal implementation details; a future rename/refactor of either
   helper inside `ticketing/service.py` (reasonable to do to a "private" symbol) will silently break
   campaigns with no signal from the ticketing module's own tests.
2. `frontend/.../[id]/page.tsx:104` defines its member-hosts query key inline
   (`['vulnerabilities', 'remediation-hosts', remediationId] as const`) instead of extending
   `queryKeys` in `frontend/src/lib/queries/keys.ts`, which the file's own header comment describes
   as "Single source of TanStack cache keys" — every other query in this phase (and the codebase
   generally) goes through that registry.

**Fix:**
```python
# ticketing/service.py — drop the leading underscore on the two symbols now
# consumed across a module boundary (e.g. extract_ticket_ref / provider_create_kwargs),
# or re-export them explicitly from a shared, public location.
```
```ts
// keys.ts
vulnerabilities: {
  ...
  remediationHosts: (remediationId: string) =>
    ['vulnerabilities', 'remediation-hosts', remediationId] as const,
},
// [id]/page.tsx
queryKey: queryKeys.vulnerabilities.remediationHosts(remediationId ?? ''),
```

---

_Reviewed: 2026-08-18T09:55:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
